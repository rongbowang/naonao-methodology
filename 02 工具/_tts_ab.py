# -*- coding: utf-8 -*-
r"""_tts_ab.py — 付费 TTS 音色 A/B：同一段台词，多家引擎多个音色，一条对比音频

## 为什么不用网页试听
网页试听是「随便一句」，我们要听的是**我们自己的稿子**——
一镜里有长句、有数字、有停顿、有转折，只有这样才能听出谁在念稿、谁在说话。

## 干什么
1. 从工程的 cues.json 里挑一镜（默认 00_hook，就是钩子，最挑音色）
2. 对每家引擎 × 每个音色 合成一遍
3. 每条前面插一句编号播报（edge 音色），再拼成一条 mp3，末尾报账（字数/耗时/估算费用）
4. 打印一张表：引擎 / 音色 / 时长 / 结果

用法：
  python _tts_ab.py --proj NO.17_等一句话               # 全部引擎全部音色
  python _tts_ab.py --proj NO.17_等一句话 --only minimax
  python _tts_ab.py --proj NO.17_等一句话 --shot 06_two --out _ab/ab2.mp3
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths          # noqa: E402
import _tts_paid as tp  # noqa: E402

SR = 44100

# 候选音色（只列免费能听到的常规款，克隆款要单独开通）
VOICES = {
    "minimax": [
        ("male-qn-qingse", "青涩青年"),
        ("male-qn-jingying", "精英青年"),
        ("male-qn-badao", "霸道少年"),
        ("audiobook_male_1", "有声书男声"),
        ("presenter_male", "主持人男声"),
        ("male-qn-daxuesheng", "大学生男声"),
    ],
    "doubao": [
        # 这些是控制台音色库里的 Speaker ID，形如 zh_male_xxx_bigtts
        ("zh_male_beijingxiaoye_moon_bigtts", "北京小爷"),
        ("zh_male_shaonianzixin_moon_bigtts", "少年自信"),
        ("zh_male_jingqiangkanye_moon_bigtts", "京腔侃爷"),
        ("zh_male_yuanboxiaoshu_moon_bigtts", "渊博小叔"),
        ("zh_male_yangguangqingnian_moon_bigtts", "阳光青年"),
        ("zh_male_silang_moon_bigtts", "四郎"),
    ],
}

PRICE = {  # 元/万字符（2026-10 刊例，只用来算账）
    "minimax": 3.5,
    "doubao": 3.0,
}


def read_wav(p):
    with wave.open(p, "rb") as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16
                          ).astype(np.float32) / 32768.0
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(axis=1)
    return a, sr


def resample(a, sr, target=SR):
    if sr == target:
        return a
    n = int(len(a) * target / sr)
    x = np.linspace(0, len(a) - 1, n)
    return np.interp(x, np.arange(len(a)), a).astype(np.float32)


def edge_say(text, out):
    """用 edge-tts 念一句编号（做对比音频里的报幕）"""
    import asyncio
    import edge_tts
    mp3 = out.replace(".wav", ".mp3")
    asyncio.run(edge_tts.Communicate(text, "zh-CN-YunyangNeural").save(mp3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", str(SR),
                    "-ac", "1", out], capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", default="2026-11-01_一百个人等一句话")
    ap.add_argument("--shot", default="", help="只跑这一镜，默认整个钩子镜")
    ap.add_argument("--only", default="", help="只跑某家引擎")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    proj = _paths.proj_dir(a.proj)
    cues = json.load(io.open(os.path.join(proj, "cues.json"), encoding="utf-8"))
    shots = []
    for c in cues:
        sid = c["id"].rsplit("_c", 1)[0]
        if not shots or shots[-1][0] != sid:
            shots.append([sid, []])
        shots[-1][1].append(c["text"])
    if a.shot:
        pick = [s for s in shots if s[0] == a.shot]
    else:
        pick = shots[:1]
    sid, lines = pick[0]
    text = "".join(lines)
    print("试听镜次: %s  (%d 字)" % (sid, len(text)))

    cfg = tp.load_cfg()
    outdir = os.path.join(proj, "_ab")
    os.makedirs(outdir, exist_ok=True)
    outmp3 = a.out or os.path.join(outdir, "ab_%s.mp3" % sid)

    engines = [e for e in VOICES if not a.only or e == a.only]
    chunks, table = [], []
    n = 0
    for eng in engines:
        c = cfg.get(eng) or {}
        if not c.get("api_key"):
            print("  跳过 %s：没配 api_key" % eng)
            continue
        for vid, label in VOICES[eng]:
            n += 1
            tag = "%d号 %s %s" % (n, eng, label)
            print("  [%d] %-8s %-38s" % (n, eng, vid), end="", flush=True)
            wav = os.path.join(outdir, "v%02d_%s.wav" % (n, vid))
            t = time.time()
            try:
                cc = dict(c)
                cc["speaker" if eng == "doubao" else "voice_id"] = vid
                sents = tp.synth(text, wav, eng, {eng: cc})
                y, sr = read_wav(wav)
                y = resample(y, sr)
                dur = len(y) / float(SR)
                intro = edge_say(tag + "。", os.path.join(outdir, "_intro.wav"))
                yi, _ = read_wav(intro)
                chunks += [yi, np.zeros(int(0.25 * SR)), y, np.zeros(int(0.7 * SR))]
                print("  %.1fs音频  %.1fs耗时  句码=%s"
                      % (dur, time.time() - t, "有" if sents else "无"))
                table.append((n, eng, label, vid, dur, "OK" if sents else "无时间码"))
            except Exception as e:
                print("  失败: %s" % str(e)[:110])
                table.append((n, eng, label, vid, 0.0, "FAIL " + str(e)[:60]))

    if not chunks:
        print("\n一条都没合成成功。先填 02 工具/_tts_key.json（跑 --check 看缺什么）")
        return 1

    y = np.concatenate(chunks)
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    tmpw = os.path.join(outdir, "_ab.wav")
    with wave.open(tmpw, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmpw, "-b:a", "160k",
                    outmp3], capture_output=True)

    print("\n%-3s %-8s %-12s %-38s %6s  %s" % ("#", "引擎", "音色", "voice_id", "时长", "备注"))
    for r in table:
        print("%-3d %-8s %-12s %-38s %6.1f  %s" % r)
    print("\n估算（本期 ~680 字）：")
    for eng in engines:
        if any(r[1] == eng and r[5] == "OK" for r in table):
            print("  %-8s 约 %.2f 元/期" % (eng, 680 * PRICE[eng] / 10000.0))
    print("\n对比音频 -> %s" % outmp3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
