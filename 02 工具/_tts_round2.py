# -*- coding: utf-8 -*-
r"""_tts_round2.py — 第二轮精调：更多音色 + 语速档 + 双音色演示

用户已选 presenter_male（主持人），说语速偏慢。
这一轮要回答三件事：
  1. 还有没有比主持人更好的？  -> 10 个音色对比
  2. 语速调到多少？            -> 1.08 / 1.12 / 1.16 三档
  3. 换音色演「别人说话」行不行？ -> 双音色演示

输出三条 mp3，每条前面有报幕。
"""
import base64
import io
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths          # noqa: E402
import _tts_paid as tp  # noqa: E402

SR = 44100
GAP = 1.3        # 请求间隔，避开 RPM 限流

VOICES = [
    ("presenter_male",                       "主持人 你选的"),
    ("Chinese_radient_storyteller_vv1",      "沙哑讲述者"),
    ("Chinese_radio_host_male_vv1",          "深夜电台"),
    ("Chinese (Mandarin)_Reliable_Executive", "沉稳高管"),
    ("Chinese (Mandarin)_Male_Announcer",    "干净播音"),
    ("Chinese (Mandarin)_Gentleman",         "绅士"),
    ("Chinese (Mandarin)_News_Anchor",       "新闻主播"),
    ("Chinese (Mandarin)_Lyrical_Voice",     "抒情男声"),
    ("Deep_Voice_Man",                       "低沉男声"),
    ("Imposing_Manner",                      "气场强"),
]


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
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def synth_one(text, out, voice, speed, model=None, emotion=None):
    cfg = tp.load_cfg()
    c = dict(cfg["minimax"])
    c["voice_id"] = voice
    c["speed"] = speed
    if model:
        c["model"] = model
    return tp.synth(text, out, "minimax", {"minimax": c})


def edge_say(text, out):
    import asyncio
    import edge_tts
    mp3 = out.replace(".wav", ".mp3")
    asyncio.run(edge_tts.Communicate(text, "zh-CN-YunyangNeural").save(mp3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", str(SR),
                    "-ac", "1", out], capture_output=True)
    return out


def join(chunks, out_mp3, tmpdir):
    y = np.concatenate(chunks)
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    w = os.path.join(tmpdir, "_j.wav")
    with wave.open(w, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", w, "-b:a", "160k", out_mp3],
                   capture_output=True)
    return out_mp3


def main():
    proj = _paths.proj_dir("NO.17_等一句话")
    outdir = os.path.join(proj, "_ab")
    os.makedirs(outdir, exist_ok=True)

    cues = json.load(io.open(os.path.join(proj, "cues.json"), encoding="utf-8"))
    by_shot = {}
    for c in cues:
        by_shot.setdefault(c["id"].rsplit("_c", 1)[0], []).append(c["text"])

    # 长句镜：有数字、有引语
    text = "".join(by_shot["03_say"])
    # 双音色演示：旁白 + 引语
    narr = by_shot["03_say"][:2]
    quote = by_shot["03_say"][2]
    rest = by_shot["03_say"][3]
    laugh = by_shot["04_laugh"][1]     # "废话。这儿谁不知道有红眼睛？"

    print("=" * 62)
    print("A. 十个音色（语速 1.12）  台词：%d 字" % len(text))
    print("=" * 62)
    chunks, rows = [], []
    intro = edge_say("音色对比。", os.path.join(outdir, "_i.wav"))
    yi, _ = read_wav(intro)
    for i, (vid, label) in enumerate(VOICES, 1):
        wav = os.path.join(outdir, "r2_%02d.wav" % i)
        t = time.time()
        try:
            s = synth_one(text, wav, vid, 1.12)
            y, sr = read_wav(wav)
            y = resample(y, sr)
            dur = len(y) / float(SR)
            ann = edge_say("%d号，%s。" % (i, label), os.path.join(outdir, "_a.wav"))
            ya, _ = read_wav(ann)
            chunks += [ya, np.zeros(int(0.2 * SR)), y, np.zeros(int(0.65 * SR))]
            print("  [%2d] %-34s %5.1fs音频 %4.1fs耗时 %s"
                  % (i, label, dur, time.time() - t, "句码✓" if s else "句码✗"))
            rows.append((i, label, vid, dur, "OK" if s else "无时间码"))
        except Exception as e:
            print("  [%2d] %-34s 失败 %s" % (i, label, str(e)[:70]))
            rows.append((i, label, vid, 0, "FAIL"))
        time.sleep(GAP)
    p1 = join(chunks, os.path.join(outdir, "R2_A_十音色.mp3"), outdir)
    print("  -> %s" % p1)

    print()
    print("=" * 62)
    print("B. 语速三档（presenter_male）")
    print("=" * 62)
    chunks = []
    for sp in [1.08, 1.12, 1.16]:
        wav = os.path.join(outdir, "sp_%s.wav" % str(sp).replace(".", ""))
        s = synth_one(text, wav, "presenter_male", sp)
        y, sr = read_wav(wav)
        y = resample(y, sr)
        dur = len(y) / float(SR)
        ann = edge_say("语速 %.2f。" % sp, os.path.join(outdir, "_a.wav"))
        ya, _ = read_wav(ann)
        chunks += [ya, np.zeros(int(0.2 * SR)), y, np.zeros(int(0.65 * SR))]
        print("  %.2f  ->  %5.2fs  (%.2f 字/秒)" % (sp, dur, len(text) / dur))
        time.sleep(GAP)
    p2 = join(chunks, os.path.join(outdir, "R2_B_语速三档.mp3"), outdir)
    print("  -> %s" % p2)

    print()
    print("=" * 62)
    print("C. 双音色演示（旁白 / 旅行者 / 岛民群嘲）")
    print("=" * 62)
    chunks = []
    plan = [
        (narr[0], "presenter_male", "旁白"),
        (narr[1], "presenter_male", "旁白"),
        (quote,   "Casual_Guy",     "旅行者说的话"),
        (rest,    "presenter_male", "旁白"),
        (laugh,   "Young_Knight",   "岛民心声"),
    ]
    for i, (line, vid, role) in enumerate(plan, 1):
        wav = os.path.join(outdir, "dual_%02d.wav" % i)
        try:
            synth_one(line, wav, vid, 1.12)
            y, sr = read_wav(wav)
            y = resample(y, sr)
            chunks += [y, np.zeros(int(0.35 * SR))]
            print("  [%d] %-10s %-26s %s" % (i, role, vid, line[:26]))
        except Exception as e:
            print("  [%d] %-10s 失败：%s" % (i, role, str(e)[:60]))
        time.sleep(GAP)
    p3 = join(chunks, os.path.join(outdir, "R2_C_双音色.mp3"), outdir)
    print("  -> %s" % p3)

    print("\n表格：")
    for r in rows:
        print("  %2d  %-34s %-40s %5.1f  %s" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
