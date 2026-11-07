# -*- coding: utf-8 -*-
r"""_voice_clean.py — 把手机录音处理成能用的干净人声

## 为什么要有这个
手机在衣柜里录的素材，问题是固定的三样：底噪、房间低频轰鸣、忽大忽小。
不上 Adobe Podcast 也能救，这条链就是干这个的。

## 用法
    python _voice_clean.py            # 处理 _voice_raw/ 下全部音频
    python _voice_clean.py a.m4a      # 处理单个文件

## 处理链（按顺序）
    1. 高通 75Hz        —— 掐掉空调/冰箱的低频轰鸣
    2. afftdn 降噪      —— 估计噪声底，压掉底噪（手机录音提升最大的一步）
    3. 250Hz -1.5dB     —— 减「柜子里那种嗡嗡」
    4. 3kHz  +2dB       —— 提人声清晰度（齿音区之前）
    5. 压缩 3:1         —— 把忽大忽小拉平
    6. 限幅 0.95        —— 防爆
    7. loudnorm -16LUFS —— 统一响度，和后面的 TTS 素材对齐

输出：_voice_clean/<原名>.wav（24kHz 单声道，克隆和剪辑都能直接用）
"""
import glob
import json
import os
import re
import subprocess
import sys

FF = r"C:\Users\13071\bin\ffmpeg.exe"
RAW = "_voice_raw"
OUT = "_voice_clean"
EXTS = (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".amr", ".flac", ".mp4")

AF = ",".join([
    "highpass=f=75",
    "afftdn=nf=-25:tn=1",
    "equalizer=f=250:width_type=h:width=200:g=-1.5",
    "equalizer=f=3000:width_type=h:width=1000:g=2",
    "acompressor=threshold=-20dB:ratio=2:attack=12:release=220:makeup=1.5",
    "alimiter=limit=0.95",
])


def measure(p):
    """测整体响度（loudnorm 第一遍）"""
    r = subprocess.run([FF, "-hide_banner", "-i", p, "-af",
                        "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True)
    e = r.stderr.decode("utf-8", "ignore")
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', e, re.S)
    return float(json.loads(m.group(0))["input_i"]) if m else None


def clean(src, dst):
    tmp = dst + ".tmp.wav"
    # 第一遍：只处理，不定响度
    r = subprocess.run([FF, "-y", "-i", src, "-af", AF, "-ar", "24000", "-ac", "1", tmp],
                       capture_output=True)
    if r.returncode:
        return False, r.stderr.decode("utf-8", "ignore")[-300:]
    # 第二遍：测出来补到 -16 LUFS（比 loudnorm 单遍准，也不会把动态抹平）
    cur = measure(tmp)
    gain = 0.0 if cur is None else max(-12.0, min(12.0, -16.0 - cur))
    r2 = subprocess.run([FF, "-y", "-i", tmp, "-af",
                         "volume=%.2fdB,alimiter=limit=0.94" % gain,
                         "-ar", "24000", "-ac", "1", dst], capture_output=True)
    try:
        os.remove(tmp)
    except Exception:
        pass
    if r2.returncode:
        return False, r2.stderr.decode("utf-8", "ignore")[-300:]
    return True, "%s LUFS -> %.1f 补齐 %+.1fdB | %.0f KB" % (
        ("%.1f" % cur) if cur is not None else "?", -16, gain, os.path.getsize(dst) / 1024)


def main():
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        os.makedirs(RAW, exist_ok=True)
        files = [p for p in glob.glob(os.path.join(RAW, "*"))
                 if p.lower().endswith(EXTS)]
    if not files:
        print("没找到音频。把录好的文件放进 %s/ 再跑一次。" % RAW)
        return

    print("处理 %d 个文件\n" % len(files))
    for src in files:
        name = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(OUT, name + ".wav")
        ok, info = clean(src, dst)
        print(("  ✅ %-28s %s" % (name, info)) if ok else ("  ❌ %-28s %s" % (name, info)))
    print("\n输出目录：%s" % OUT)


if __name__ == "__main__":
    main()
