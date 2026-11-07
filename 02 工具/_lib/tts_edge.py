# -*- coding: utf-8 -*-
"""
批量 TTS：逐句合成 -> 输出每句时长 -> 拼接镜头旁白 -> 精确字幕时间轴。

用法:
    python tts_edge.py cues.json outdir/ --voice zh-CN-YunyangNeural --rate "+8%"

输入 cues.json:
    [{"id": "s01_c0", "text": "一句旁白"}, ...]
    id 命名建议: {镜头id}_c{序号}

输出:
    outdir/cues/*.wav              每句音频
    outdir/cues_meta.json          [{id, text, dur}]
    outdir/shots/{镜头id}.wav      按镜头拼接的整段旁白
    outdir/shot_meta.json          镜头时长 + 句级字幕时间轴（相对镜头起点）

音色 --voice（默认 zh-CN-YunyangNeural「云扬」，账号固定音色，勿改）:
    在线(需联网, 更自然):
      zh-CN-YunyangNeural   男 专业播报  <- 账号默认首选
      zh-CN-YunjianNeural   男 浑厚激情
      zh-CN-YunxiNeural     男 阳光青年
      zh-CN-YunxiaNeural    男 少年感
      zh-CN-XiaoxiaoNeural  女 温暖
      zh-CN-XiaoyiNeural    女 活泼
    本地离线(音色较平淡):
      local:Kangkang   local:Huihui   local:Yaoyao
"""
import argparse, asyncio, json, os, subprocess, sys, wave

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
# 只替换文件名部分，不能把目录里的 ffmpeg-9.0.2 也替换掉
_d = os.path.dirname(FFMPEG)
_b = os.path.basename(FFMPEG).replace("ffmpeg", "ffprobe")
FFPROBE = os.path.join(_d, _b) if _d else _b
SR = 44100

# 句尾标点 -> 追加停顿（秒）—— 舒适语速 + 极紧气口版（2026-10-17 再压一档）：
# 语速保持 +8%（不赶字），靠更短的气口撑住节奏；用户反馈"停顿和空白还是太长"
PAUSE = {"，": 0.055, "、": 0.03, "。": 0.09, "；": 0.08, "！": 0.09, "？": 0.10,
         "：": 0.035, "…": 0.07}
BASE_GAP = 0.02
SHOT_GAP = 0.14          # 镜头与镜头之间的呼吸（再压一档）


def probe(path):
    r = subprocess.run([FFPROBE, "-v", "error",
                        "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def to_wav(src, dst):
    subprocess.run([FFMPEG, "-y", "-i", src, "-ar", str(SR), "-ac", "1", dst],
                   capture_output=True)
    return dst


# ---------------- 本地 WinRT (离线) ----------------
async def synth_local(text, voice, path):
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader
    s = SpeechSynthesizer()
    tag = "" if voice == "Kangkang" else '<voice name="Microsoft %s">%%s</voice>' % voice
    prate = os.environ.get("TTS_RATE", "1.05")
    ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/Synthesis" '
            'xml:lang="zh-CN"><prosody rate="%s">%s</prosody></speak>') % (
        prate, tag % text if tag else text)
    st = await s.synthesize_ssml_to_stream_async(ssml)
    n = int(st.size)
    r = DataReader(st.get_input_stream_at(0))
    await r.load_async(n)
    buf = r.read_buffer(n)
    try:
        data = bytes(memoryview(buf))
    except Exception:
        data = bytes(buf)
    raw = path + ".raw"
    open(raw, "wb").write(data)
    # OneCore 输出 16kHz / 16bit / mono
    subprocess.run([FFMPEG, "-y", "-f", "s16le", "-ar", "16000", "-ac", "1",
                    "-i", raw, "-ar", str(SR), path], capture_output=True)
    os.remove(raw)


# ---------------- edge-tts (在线) ----------------
async def synth_edge(text, voice, path, rate, pitch):
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    mp3 = path + ".mp3"
    await c.save(mp3)
    to_wav(mp3, path)
    os.remove(mp3)


async def run(cues, outdir, voice, rate, pitch):
    cue_dir = os.path.join(outdir, "cues")
    os.makedirs(cue_dir, exist_ok=True)
    metas = []
    for c in cues:
        wav = os.path.join(cue_dir, c["id"] + ".wav")
        try:
            if voice.startswith("local:"):
                await synth_local(c["text"], voice.split(":", 1)[1], wav)
            else:
                await synth_edge(c["text"], voice, wav, rate, pitch)
        except Exception as e:
            print("  !! TTS failed %s: %s" % (c["id"], e))
            continue
        d = probe(wav)
        metas.append({"id": c["id"], "text": c["text"], "dur": d})
        print("  %-12s %.2fs  %s" % (c["id"], d, c["text"][:26]))
    json.dump(metas, open(os.path.join(outdir, "cues_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- 按镜头拼接 ----
    shot_dir = os.path.join(outdir, "shots")
    os.makedirs(shot_dir, exist_ok=True)
    shots = {}
    for m in metas:
        sid = m["id"].rsplit("_c", 1)[0]
        shots.setdefault(sid, []).append(m)

    shot_meta = {}
    for sid, items in shots.items():
        chunks, timeline, t = [], [], 0.0
        for it in items:
            with wave.open(os.path.join(cue_dir, it["id"] + ".wav"), "rb") as w:
                a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16
                                  ).astype(np.float32) / 32768.0
            chunks.append(a)
            timeline.append({"text": it["text"], "g0": round(t, 3),
                             "g1": round(t + it["dur"], 3)})
            t += it["dur"]
            tail = it["text"][-1] if it["text"] else ""
            gap = PAUSE.get(tail, BASE_GAP)
            chunks.append(np.zeros(int(gap * SR)))
            t += gap
        total = t
        y = np.concatenate(chunks) if chunks else np.zeros(1)
        y = np.concatenate([y, np.zeros(int(0.12 * SR))])
        pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16)
        out = os.path.join(shot_dir, sid + ".wav")
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        shot_meta[sid] = {"len": round(total, 3), "cues": timeline}
        print("  [shot] %-16s %.2fs  %d 句" % (sid, total, len(items)))

    json.dump(shot_meta, open(os.path.join(outdir, "shot_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nDONE  句数=%d  镜头=%d" % (len(metas), len(shot_meta)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cues")
    ap.add_argument("outdir")
    ap.add_argument("--voice", default="zh-CN-YunyangNeural")
    ap.add_argument("--rate", default="+8%")
    ap.add_argument("--pitch", default="+0Hz")
    a = ap.parse_args()
    cues = json.load(open(a.cues, encoding="utf-8"))
    os.makedirs(a.outdir, exist_ok=True)
    asyncio.run(run(cues, a.outdir, a.voice, a.rate, a.pitch))


if __name__ == "__main__":
    main()
