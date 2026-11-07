# -*- coding: utf-8 -*-
r"""_tts_paid.py — 付费 TTS 接入层（MiniMax / 豆包），输出与 edge-tts 完全兼容

## 为什么要有这一层
edge-tts 免费但只有「播音腔」，中文自然度 60 分。
付费两家（MiniMax / 豆包）是 85 分档，且都**返回句级时间戳**——
这一点是硬门槛，没有时间码，字幕就错位，整条管线白做。

## 两家都返回时间码，但形式不同
  MiniMax  REST，一次 POST 拿完整 JSON
           data.audio         hex 编码的 mp3
           data.subtitle_file 「字幕 JSON 的下载链接」——必须马上下载，
                              过一会就过期。句级，毫秒时间戳
  豆包     HTTP Chunked (NDJSON)，一行一个 JSON
           每行 {"code":0,"data":"<base64 mp3 分片>"}，最后 {"code":20000000}
           行内若带 sentence.words[] 就是字级时间戳（秒）

## 契约（tts_whole.py 只认这个）
  synth(text, out_wav) -> [[t0, t1, text], ...] 或 None
  返回 None = 没拿到时间码 → 上游自动退回「静音检测 + DP」，字幕仍能出，只是精度低一档

## 配置文件（不进库，只在本机）
  02 工具/_tts_key.json
  {
    "minimax": {"api_key": "...", "model": "speech-2.8-hd",
                "voice_id": "male-qn-qingse", "speed": 1.08},
    "doubao":  {"api_key": "...", "speaker": "zh_male_..._bigtts",
                "resource_id": "seed-tts-2.0", "speech_rate": 8}
  }

用法：
  python _tts_paid.py --check                     # 只查配置齐不齐，不花钱
  python _tts_paid.py --engine minimax --text "测试一句" --out a.wav
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, "_tts_key.json")
SR_OUT = 44100
TIMEOUT = 120

MM_URL_CN = "https://api.minimaxi.com/v1/t2a_v2"
MM_URL_INTL = "https://api.minimax.io/v1/t2a_v2"
DB_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


# ------------------------------------------------------------------ 配置
def load_cfg(path=KEYFILE):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg, path=KEYFILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return path


# ------------------------------------------------------------------ 工具
def to_wav(src_bytes, out_wav, suffix=".mp3"):
    """字节流 -> 44.1k 单声道 wav。共享盘 safe-delete 会拦 os.remove，走 tempfile 兜底"""
    d = tempfile.mkdtemp(prefix="ttsp_")
    src = os.path.join(d, "a" + suffix)
    with open(src, "wb") as f:
        f.write(src_bytes)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                        "-ar", str(SR_OUT), "-ac", "1", out_wav],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 失败: " + r.stderr[-300:])
    return out_wav


_norm = lambda s: __import__("re").sub(r"\s+", "", s or "")  # noqa: E731


def _mk_sents(pairs, min_dur=0.04):
    """[(t0,t1,txt)] -> 排好序、去掉零长度、夹住负值。

    min_dur 对**字级**必须传 0：实测单字最短约 0.039s，用 0.04 会被整片过滤，
    上游按字符游标累加时长度对不上，就会退回静音兜底。
    """
    out = []
    for t0, t1, txt in pairs:
        if t1 - t0 < min_dur or not txt:
            continue
        out.append([round(max(0.0, t0), 3), round(max(0.0, t1), 3), txt])
    out.sort(key=lambda x: x[0])
    return out or None


# ------------------------------------------------------------------ MiniMax
def _mm_post(url, body, key, tries=5):
    """MiniMax POST，带限流重试。

    1002 rate limit exceeded(RPM) 是**并发/频率**限制，不是余额问题。
    分段合成时一镜一个请求，很快撞上，所以退避重试：3s / 6s / 12s / 20s。
    """
    last = None
    for i in range(tries):
        r = requests.post(url, json=body, timeout=TIMEOUT,
                          headers={"Authorization": "Bearer " + key,
                                   "Content-Type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError("MiniMax HTTP %d: %s"
                               % (r.status_code, r.text[:300]))
        j = r.json()
        code = (j.get("base_resp") or {}).get("status_code")
        if code in (0, None):
            return j
        msg = (j.get("base_resp") or {}).get("status_msg") or ""
        if code == 1002 or "rate limit" in msg.lower():
            wait = [3, 6, 12, 20, 30][min(i, 4)]
            print("    [限流] %ds 后重试（%d/%d）" % (wait, i + 1, tries))
            time.sleep(wait)
            last = msg
            continue
        return j
    raise RuntimeError("MiniMax 连续限流: %s" % last)


def synth_minimax(text, out_wav, cfg=None, lines=None):
    """MiniMax 同步语音合成 T2A v2。返回句级时间码。"""
    c = (cfg or {}).get("minimax") or {}
    key = c.get("api_key") or os.environ.get("MINIMAX_API_KEY")
    if not key:
        raise RuntimeError("缺 MiniMax api_key（_tts_key.json 的 minimax.api_key）")
    url = c.get("url") or MM_URL_CN
    gid = str(c.get("group_id") or "").strip()
    if gid:
        url = url + ("&" if "?" in url else "?") + "GroupId=" + gid

    body = {
        "model": c.get("model", "speech-2.8-hd"),
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": c.get("voice_id", "male-qn-qingse"),
            "speed": float(c.get("speed", 1.08)),
            "vol": float(c.get("vol", 1.0)),
            "pitch": int(c.get("pitch", 0)),
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        # 实测：sentence 实际按「≤50 字」切段，不是按句号。87 字一镜只回 1 段、
        # 覆盖 13.7 秒跨 3 行台词 → 字幕必错位。所以改 word 拿字级时间戳。
        "subtitle_enable": True,
        "subtitle_type": "word",
        "output_format": "hex",
        "language_boost": c.get("language_boost", "Chinese"),
    }
    j = _mm_post(url, body, key)
    br = j.get("base_resp") or {}
    if br.get("status_code") not in (0, None):
        raise RuntimeError("MiniMax 业务错误 %s: %s"
                           % (br.get("status_code"), br.get("status_msg")))

    data = j.get("data") or {}
    audio_hex = data.get("audio")
    if not audio_hex:
        raise RuntimeError("MiniMax 没返回音频: %s" % json.dumps(j)[:300])
    to_wav(bytes.fromhex(audio_hex), out_wav)

    # 字幕：subtitle_file 是下载链接，会过期，立刻取
    sents = None
    sf = data.get("subtitle_file")
    if sf:
        try:
            sr = requests.get(sf, timeout=60)
            ws = _all_words(sr.text)
            if lines and ws:
                sents = rows_by_charpos(ws, lines)
            if sents is None:
                sents = parse_word_subtitle(sr.text, text)
            if sents is None:                  # 词级没解析出来 -> 退回句级
                sents = parse_subtitle(sr.text)
        except Exception as e:
            print("  [warn] 字幕下载失败（退回静音兜底）: %s" % str(e)[:120])
    return sents


def _all_words(txt):
    """字幕 JSON -> 全部 timestamped_words（原始 dict，带 word_begin）"""
    try:
        segs = json.loads(txt)
    except Exception:
        return []
    if not isinstance(segs, list):
        return []
    out = []
    for seg in segs:
        out.extend(seg.get("timestamped_words") or [])
    out.sort(key=lambda w: (w.get("time_begin") or 0))
    return out


def rows_by_charpos(ws, lines):
    """用 word_begin 的**绝对字符位置**把字时间归到台词行。

    实测（NO.17 全片 782 字 / 778 个 word）：末个 word_end == len(text)，
    且 778/778 个 word 的 [word_begin:word_end] 与原文完全吻合。
    所以位置是可信的，不要用「拼字符串再比对」——`——` 会被 API 规范化成 `—`，
    一比对就判不一致，白白退回静音兜底。
    """
    cum, acc = [], 0
    for ln in lines:
        acc += len(ln)          # 含空格，与 word_begin 的坐标系一致
        cum.append(acc)
    spans = [None] * len(lines)
    for w in ws:
        b, t0, t1 = w.get("word_begin"), w.get("time_begin"), w.get("time_end")
        if b is None or t0 is None or t1 is None:
            continue
        li = 0
        while li < len(lines) - 1 and b >= cum[li]:
            li += 1
        if spans[li] is None:
            spans[li] = [t0, t1]
        else:
            spans[li][0] = min(spans[li][0], t0)
            spans[li][1] = max(spans[li][1], t1)
    if any(s is None for s in spans):
        return None
    return [[round(a / 1000.0, 3), round(b / 1000.0, 3), lines[i]]
            for i, (a, b) in enumerate(spans)]


def parse_word_subtitle(txt, source_text=""):
    """MiniMax 词级字幕 -> [[t0,t1,字]]（秒）。

    结构：[{"text": 整段, "timestamped_words":[{"word":"九","word_begin":0,
            "word_end":1,"time_begin":39.5,"time_end":237.0}, ...]}]

    返回**逐字条目**，交给上游 spans_by_sentence 按字符游标归行，
    每行取 min(起点)/max(终点) = 该行真实发声区间。
    同时校验「拼起来的字 == 原文」，不一致返回 None（宁可退回静音兜底，也不要错位字幕）。
    """
    try:
        segs = json.loads(txt)
    except Exception:
        return None
    if not isinstance(segs, list):
        return None
    pairs = []
    for seg in segs:
        for w in (seg.get("timestamped_words") or []):
            t0, t1, wd = w.get("time_begin"), w.get("time_end"), w.get("word")
            if t0 is None or t1 is None or not wd:
                continue
            pairs.append((float(t0) / 1000.0, float(t1) / 1000.0, wd))
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0])
    if source_text:
        joined, src = _norm("".join(p[2] for p in pairs)), _norm(source_text)
        if joined != src:
            print("  [warn] 词级字幕与原文不一致（%d vs %d 字），退回句级"
                  % (len(joined), len(src)))
            return None
    return _mk_sents(pairs, min_dur=0.0)


def parse_subtitle(txt):
    """MiniMax 字幕 JSON -> [[t0,t1,text]]。字段名做过兼容：
    句级常见 begin_time/end_time 或 start_time/end_time，单位毫秒。
    """
    try:
        j = json.loads(txt)
    except Exception:
        return None

    def walk(o):
        if isinstance(o, list):
            for x in o:
                yield from walk(x)
        elif isinstance(o, dict):
            keys = set(o.keys())
            t0 = _first(o, ("begin_time", "start_time", "time_begin", "start"))
            t1 = _first(o, ("end_time", "time_end", "end"))
            tx = _first(o, ("text", "sentence", "word"))
            if t0 is not None and t1 is not None and isinstance(tx, str):
                yield (float(t0), float(t1), tx)
                return
            for v in o.values():
                yield from walk(v)

    cand = list(walk(j))
    if not cand:
        return None
    # 毫秒 -> 秒（若最大值 > 200 认为单位是毫秒）
    if max(c[1] for c in cand) > 200:
        cand = [(a / 1000.0, b / 1000.0, t) for a, b, t in cand]
    return _mk_sents(cand)


def _first(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


# ------------------------------------------------------------------ 豆包
def synth_doubao(text, out_wav, cfg=None):
    """豆包语音合成大模型 2.0（HTTP Chunked / NDJSON）。返回句级（或字级拼句）时间码。"""
    c = (cfg or {}).get("doubao") or {}
    key = c.get("api_key") or os.environ.get("DOUBAO_API_KEY")
    if not key:
        raise RuntimeError("缺豆包 api_key（_tts_key.json 的 doubao.api_key）")
    speaker = c.get("speaker")
    if not speaker:
        raise RuntimeError("缺豆包 speaker（控制台 > 音色库里的音色 ID）")

    headers = {
        "X-Api-Key": key,
        "X-Api-Resource-Id": c.get("resource_id", "seed-tts-2.0"),
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Control-Require-Usage-Tokens-Return": "*",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    body = {
        "user": {"uid": c.get("uid", "naonao")},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
                "speech_rate": int(c.get("speech_rate", 8)),
            },
        },
    }
    s = requests.Session()
    r = s.post(DB_URL, headers=headers, json=body, stream=True, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError("豆包 HTTP %d: %s" % (r.status_code, r.text[:300]))

    buf, words, blk = bytearray(), [], None
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            j = json.loads(line)
        except Exception:
            continue
        code = j.get("code", 0)
        if code == 20000000:
            break
        if code != 0:
            raise RuntimeError("豆包错误 %s: %s" % (code, j.get("message")))
        audio = j.get("data")
        if audio:
            try:
                buf.extend(base64.b64decode(audio))
            except Exception:
                pass
        sen = j.get("sentence")
        if isinstance(sen, dict):
            blk = blk or {"t0": None, "t1": None, "txt": ""}
            for w in (sen.get("words") or []):
                st, et, wd = w.get("startTime"), w.get("endTime"), w.get("word")
                if st is None or et is None or not wd:
                    continue
                words.append((float(st), float(et), wd))
            if sen.get("text"):
                blk["txt"] += sen["text"]

    if len(buf) < 2000:
        raise RuntimeError("豆包音频太短 %d 字节" % len(buf))
    to_wav(bytes(buf), out_wav)

    # 豆包给的是**字级**时间戳，要拼成行。先按标点把字串成句，
    # 再用「字幕行文本」去匹配（tts_whole 里还会按字符游标二次归行）。
    if not words:
        return None
    return _words_to_sents(words)


def _words_to_sents(words):
    """字级时间戳按标点聚成句。words 是 [(t0,t1,字)]，已按时间排。"""
    words.sort(key=lambda x: x[0])
    pairs, cur = [], {"txt": "", "t0": None, "t1": None}
    END = "。！？；…"
    for t0, t1, w in words:
        if cur["t0"] is None:
            cur["t0"] = t0
        cur["txt"] += w
        cur["t1"] = t1
        if w.strip() and w.strip()[-1] in END:
            pairs.append((cur["t0"], cur["t1"], cur["txt"]))
            cur = {"txt": "", "t0": None, "t1": None}
    if cur["txt"]:
        pairs.append((cur["t0"], cur["t1"], cur["txt"]))
    return _mk_sents(pairs)


# ------------------------------------------------------------------ 统一入口
ENGINES = {"minimax": synth_minimax, "doubao": synth_doubao}


def synth_segments(rows, out_wav, engine="minimax", cfg=None, gap=0.22):
    """多音色 / 多情绪分段合成。

    rows: [{"text": "...", "voice": "Casual_Guy", "emotion": "happy"}, ...]
           voice / emotion 缺省就用 _tts_key.json 里的默认值。

    把**连续相同 (voice, emotion, speed, pitch)** 的行并成一段一口气合成——
    同一音色的相邻句子不能拆开合成，否则句尾会一律降调、停顿等长（就是 tts_resume 的老毛病）。

    返回 [[t0, t1, 行文本]]（相对整条 out_wav 的秒数），交给上层 spans_by_sentence 直接命中。
    """
    import wave as _wave

    import numpy as _np

    cfg = cfg or load_cfg()
    if not rows:
        raise RuntimeError("rows 为空")

    def keyof(r):
        return (r.get("voice"), r.get("emotion"),
                r.get("speed"), r.get("pitch"))

    groups = []
    for r in rows:
        k = keyof(r)
        if groups and groups[-1][0] == k:
            groups[-1][1].append(r)
        else:
            groups.append([k, [r]])

    import tempfile as _tempfile
    td = _tempfile.mkdtemp(prefix="ttsg_")
    pieces, spans, offset = [], [], 0.0

    for gi, (k, items) in enumerate(groups):
        voice, emotion, speed, pitch = k
        sub = dict(cfg.get(engine) or {})
        if voice:
            sub["voice_id"] = voice
        if speed:
            sub["speed"] = float(speed)
        if pitch is not None:
            sub["pitch"] = int(pitch)
        lines = [it["text"] for it in items]
        text = "".join(lines)
        seg_wav = os.path.join(td, "g%02d.wav" % gi)

        # 逐段调底层引擎（目前只对 minimax 支持 emotion；豆包传了就忽略）
        if engine == "minimax":
            s = synth_minimax(text, seg_wav, {engine: sub}, lines)
        else:
            s = synth(text, seg_wav, engine, {engine: sub}, lines)

        with _wave.open(seg_wav, "rb") as w:
            sr = w.getframerate()
            a = _np.frombuffer(w.readframes(w.getnframes()), dtype=_np.int16
                               ).astype(_np.float32) / 32768.0
            if w.getnchannels() > 1:
                a = a.reshape(-1, w.getnchannels()).mean(axis=1)
        dur = len(a) / float(sr)
        pieces.append(a)
        pieces.append(_np.zeros(int(gap * sr), dtype=_np.float32))

        # 段内时间码 -> 加上偏移
        if s is None:
            raise RuntimeError("第 %d 段（voice=%s）没拿到时间码，无法拼接"
                               % (gi + 1, voice or "默认"))
        for (t0, t1, tx) in s:
            spans.append([round(offset + t0, 3), round(offset + t1, 3), tx])
        offset += dur + gap
        print("    段%d voice=%-32s emotion=%-9s %5.2fs %d句"
              % (gi + 1, voice or "默认", emotion or "-", dur, len(items)))
        if gi < len(groups) - 1:
            time.sleep(1.2)          # 段间隔，避开 RPM 限流

    y = _np.concatenate(pieces)
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)) or ".", exist_ok=True)
    pcm = (_np.clip(y, -1, 1) * 32767).astype(_np.int16)
    with _wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR_OUT)
        w.writeframes(pcm.tobytes())
    return spans


def synth(text, out_wav, engine="minimax", cfg=None, lines=None):
    """统一入口。lines 给了就返回**行级**时间码（[[t0,t1,行文本]]），
    比字级更准，因为直接按 word_begin 字符位置切行，不经过字符串比较。
    """
    # cfg=None 时自动读 _tts_key.json（tts_whole.py 传的就是 None）
    if cfg is None:
        cfg = load_cfg()
    fn = ENGINES.get(engine)
    if fn is None:
        raise RuntimeError("未知引擎 %s，可选 %s" % (engine, list(ENGINES)))
    if engine == "minimax":
        return fn(text, out_wav, cfg, lines)
    return fn(text, out_wav, cfg)


def check(cfg=None):
    """体检：只查配置，不花钱。"""
    cfg = cfg if cfg is not None else load_cfg()
    print("配置文件:", KEYFILE, "存在" if os.path.exists(KEYFILE) else "不存在")
    ok = 0
    for eng in ENGINES:
        c = cfg.get(eng) or {}
        # 2026-10-31 实测：MiniMax T2A v2 只需 Bearer key；不传 GroupId 反而通，
        # 传「用户ID」当 GroupId 会 1004 token not match group。故 group_id 选填。
        need = ["api_key"] + (["speaker"] if eng == "doubao" else ["voice_id"])
        miss = [k for k in need if not c.get(k)]
        if miss:
            print("  %-8s 缺 %s" % (eng, ", ".join(miss)))
        else:
            print("  %-8s 就绪  voice=%s" % (eng, c.get("voice_id") or c.get("speaker")))
            ok += 1
    print("可用引擎: %d/%d" % (ok, len(ENGINES)))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--engine", default="minimax", choices=list(ENGINES))
    ap.add_argument("--text", default="")
    ap.add_argument("--textfile", default="")
    ap.add_argument("--out", default="tts_out.wav")
    ap.add_argument("--voice", default="", help="临时覆盖 voice_id / speaker")
    a = ap.parse_args()

    cfg = load_cfg()
    if a.check:
        check(cfg)
        return
    text = a.text
    if a.textfile:
        with open(a.textfile, encoding="utf-8") as f:
            text = f.read().strip()
    if not text:
        raise SystemExit("要 --text 或 --textfile")
    if a.voice:
        k = "speaker" if a.engine == "doubao" else "voice_id"
        cfg.setdefault(a.engine, {})[k] = a.voice

    t = time.time()
    sents = synth(text, a.out, a.engine, cfg)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", a.out],
                         capture_output=True, text=True).stdout.strip()
    print("引擎=%s  字符=%d  耗时=%.1fs  音频=%ss  句=%s  -> %s"
          % (a.engine, len(text), time.time() - t, dur,
             len(sents) if sents else "无(将走静音兜底)", a.out))
    if sents:
        for s in sents[:5]:
            print("   %6.2f~%6.2f  %s" % (s[0], s[1], s[2][:36]))


if __name__ == "__main__":
    sys.exit(main())
