# -*- coding: utf-8 -*-
"""生成基础音效（纯 numpy 合成，不依赖任何素材库）。
输出到 工程文件/sfx/*.wav

用法: python make_sfx.py
"""
import os
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfx")


def _band_noise(n, lo, hi, seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def crowd(dur=3.0, seed=7):
    """人群嘈杂 / 叽叽喳喳：带通噪声 + 随机音节包络"""
    n = int(SR * dur)
    base = _band_noise(n, 300, 2400, seed)
    env = 0.35 + 0.65 * np.abs(np.sin(np.linspace(0, 17, n)))   # 起伏
    syl = np.zeros(n)
    rng = np.random.default_rng(seed + 1)
    t = 0
    while t < n:
        ln = int(SR * rng.uniform(0.06, 0.16))
        if t + ln > n:
            break
        seg = _band_noise(ln, 600, 3200, seed + t)
        w = np.hanning(ln)
        syl[t:t + ln] += seg * w * rng.uniform(0.4, 1.0)
        t += ln + int(SR * rng.uniform(0.02, 0.10))
    y = 0.55 * base * env + 0.75 * syl
    return y / (np.abs(y).max() + 1e-9)


def scribble(dur=2.4, seed=11):
    """笔尖沙沙：高频短促噪声串"""
    n = int(SR * dur)
    y = np.zeros(n)
    rng = np.random.default_rng(seed)
    t = 0
    while t < n:
        ln = int(SR * rng.uniform(0.03, 0.09))
        if t + ln > n:
            break
        seg = _band_noise(ln, 2500, 7000, seed + t)
        y[t:t + ln] += seg * np.hanning(ln) * rng.uniform(0.5, 1.0)
        t += ln + int(SR * rng.uniform(0.01, 0.05))
    return y / (np.abs(y).max() + 1e-9)


def whoosh(dur=0.55, seed=21):
    """转场风声：频带随时间下扫"""
    n = int(SR * dur)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    y = np.zeros(n)
    for k in range(24):
        a, b = int(n * k / 24), int(n * (k + 1) / 24)
        lo = 2600 - 2000 * (k / 24.0)
        hi = lo + 2200
        Xk = X.copy()
        Xk[(f < max(lo, 60)) | (f > hi)] = 0
        y[a:b] = np.fft.irfft(Xk, n)[a:b]
    y *= np.hanning(n)
    return y / (np.abs(y).max() + 1e-9)


def ding(dur=0.9, seed=31):
    """提示音：两个正弦泛音 + 快衰减"""
    n = int(SR * dur)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * 1180 * t) + 0.45 * np.sin(2 * np.pi * 1770 * t)
         + 0.22 * np.sin(2 * np.pi * 2360 * t))
    y *= np.exp(-6.0 * t)
    return y / (np.abs(y).max() + 1e-9)


def stamp(dur=0.42, seed=41):
    """盖章 / 判定：低频冲击 + 短噪声"""
    n = int(SR * dur)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * 120 * t) * np.exp(-14.0 * t)
    tick = _band_noise(n, 900, 4200, seed) * np.exp(-40.0 * t)
    y = 0.9 * thud + 0.7 * tick
    return y / (np.abs(y).max() + 1e-9)


def write(name, y, gain=0.85):
    os.makedirs(OUT, exist_ok=True)
    pcm = (np.clip(y * gain, -1, 1) * 32767).astype(np.int16)
    p = os.path.join(OUT, name)
    with wave.open(p, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("  %-14s %.2fs" % (name, len(y) / SR))


if __name__ == "__main__":
    print("生成音效 ->", OUT)
    write("crowd.wav", crowd())
    write("scribble.wav", scribble())
    write("whoosh.wav", whoosh())
    write("ding.wav", ding())
    write("stamp.wav", stamp())
    print("DONE")
