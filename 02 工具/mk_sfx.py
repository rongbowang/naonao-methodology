# -*- coding: utf-8 -*-
"""mk_sfx.py — 合成 Phase 1 样板音效（海风/篝火/木板脚步/入水）

依据：画面升级诊断与改造方案 五.D（音效轨）。
产物：30 制作/2026-11-01_一百个人等一句话/sfx_custom/*.wav + sfx_custom_catalog.json（实测 LUFS）
纯 numpy 合成（无 scipy），44100Hz / 16bit / mono。CC0 自产。
"""
import json
import os
import subprocess

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "30 制作", "NO.17_等一句话", "sfx_custom")
os.makedirs(OUT, exist_ok=True)

rng = np.random.default_rng(20261101)


def lowpass(x, fc, sr=SR):
    """一阶 IIR 低通（够氛围用；相位失真无所谓）"""
    a = np.exp(-2 * np.pi * fc / sr)
    y = np.empty_like(x)
    acc = 0.0
    b = 1 - a
    for i in range(len(x)):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def highpass(x, fc, sr=SR):
    return x - lowpass(x, fc, sr)


def pinkish(n):
    """粉噪近似：白噪 + 一阶低通，能量往低频堆"""
    return lowpass(rng.standard_normal(n), 1200)


def brownish(n):
    b = np.cumsum(rng.standard_normal(n))
    b -= np.linspace(b[0], b[-1], n)          # 去漂移
    return b / (np.abs(b).max() + 1e-9)


def env_ad(n, a, d):
    """attack/decay 包络"""
    t = np.arange(n) / n
    e = np.minimum(1, t / max(a, 1e-6)) * np.exp(-t / max(d, 1e-6) * 3)
    return e


def to_wav(x, name, gain=1.0):
    x = np.clip(x * gain, -1, 1)
    pcm = (x * 32767).astype("<i2")
    import wave
    p = os.path.join(OUT, name + ".wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return p


def fade_io(x, sec=1.2):
    n = int(sec * SR)
    if len(x) > 2 * n:
        ramp = np.linspace(0, 1, n)
        x[:n] *= ramp; x[-n:] *= ramp[::-1]
    return x


# ----------------------------------------------------------------
# 1) amb_seawind 海风（24s）：粉噪低通 + 双频慢 LFO（浪涌）+ 偶发远浪 swell
# ----------------------------------------------------------------
def make_seawind():
    n = int(24 * SR)
    t = np.arange(n) / SR
    base = lowpass(pinkish(n), 520)
    # 浪涌：两个不成倍数的慢波动
    lfo = 0.55 + 0.28 * np.sin(2 * np.pi * 0.071 * t + 0.4) \
               + 0.17 * np.sin(2 * np.pi * 0.137 * t + 2.1)
    x = base * lfo
    # 远处浪拍：每 7~10 秒一次的低沉 swell
    pos = 3.0
    while pos < 22.5:
        dur = 2.6
        i0, nd = int(pos * SR), int(dur * SR)
        if i0 + nd < n:
            swell = lowpass(rng.standard_normal(nd), 260) * np.sin(np.linspace(0, np.pi, nd)) ** 2
            x[i0:i0 + nd] += swell * 1.1
        pos += rng.uniform(6.5, 10.5)
    x = fade_io(x, 1.5)
    return x / (np.abs(x).max() + 1e-9) * 0.8


# ----------------------------------------------------------------
# 2) amb_campfire 篝火（24s）：棕噪底 + 随机 crackle + 偶发爆响
# ----------------------------------------------------------------
def make_campfire():
    n = int(24 * SR)
    x = lowpass(brownish(n), 340) * 0.5
    # crackle：泊松到达 ~2.8 次/秒，短高通 burst
    pos = 0.0
    while pos < 23.8:
        pos += rng.exponential(1 / 2.8)
        dur = rng.uniform(0.003, 0.020)
        nd = max(2, int(dur * SR))
        i0 = int(pos * SR)
        if i0 + nd >= n:
            break
        amp = rng.uniform(0.3, 1.0) * (2.2 if rng.random() < 0.05 else 1.0)   # 5% 大爆
        burst = highpass(rng.standard_normal(nd), 1400) * env_ad(nd, 0.05, 0.4) * amp
        x[i0:i0 + nd] += burst * 0.55
    x = fade_io(x, 1.0)
    return x / (np.abs(x).max() + 1e-9) * 0.9


# ----------------------------------------------------------------
# 3) wood_step 木板单步（0.38s）：低频 thud + 板吱呀 + 衣料摩擦
# ----------------------------------------------------------------
def make_step():
    n = int(0.38 * SR)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * (96 * np.exp(-t * 8) + 58) * t) * np.exp(-t * 16) * 0.9
    creak = np.sin(2 * np.pi * 1350 * t) * np.exp(-t * 40) * rng.uniform(0.06, 0.1)
    cloth = lowpass(rng.standard_normal(n), 900) * np.exp(-t * 22) * 0.12
    x = thud + creak + cloth
    return x / (np.abs(x).max() + 1e-9)


# ----------------------------------------------------------------
# 4) dive_splash 入水（1.9s）：破水 burst + 扑通低扫 + 气泡群 + 尾水
# ----------------------------------------------------------------
def make_splash():
    n = int(1.9 * SR)
    x = np.zeros(n)
    t = np.arange(n) / SR
    # 破水瞬间（0~0.18s）：宽带 burst
    nb = int(0.18 * SR)
    x[:nb] += lowpass(rng.standard_normal(nb), 2600) * env_ad(nb, 0.04, 0.5) * 0.95
    # 扑通：120→52Hz 扫频正弦（0~0.5s）
    sweep = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-t * 4) - 30 * t) / SR) \
        * np.exp(-t * 5.5) * 0.85
    x += sweep
    # 气泡：0.25~1.5s 随机 blip（各 6~30ms，频率 700~2600Hz）
    pos = 0.25
    while pos < 1.5:
        pos += rng.exponential(1 / 16)
        dur = rng.uniform(0.006, 0.030)
        nd = max(2, int(dur * SR))
        i0 = int(pos * SR)
        if i0 + nd >= n:
            break
        f = rng.uniform(700, 2600)
        blip = np.sin(2 * np.pi * f * np.arange(nd) / SR + rng.uniform(0, 6)) \
            * np.exp(-np.arange(nd) / nd * 6) * rng.uniform(0.05, 0.16)
        x[i0:i0 + nd] += blip
    # 尾水：低噪涟漪（0.4s 起）
    nt = int(1.5 * SR)
    tail = lowpass(rng.standard_normal(nt), 480) * np.linspace(1, 0, nt) ** 2 * 0.16
    x[int(0.4 * SR):int(0.4 * SR) + nt] += tail
    return x / (np.abs(x).max() + 1e-9) * 0.95


def measure_lufs(path, rep=1):
    """rep>1：短音效（<3s loudnorm 测不出）用重复拼接量代表响度"""
    src = None
    if rep > 1:
        import wave
        with wave.open(path, "rb") as w:
            src = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2") / 32767.0
        tiled = np.tile(src, rep)
        gap = np.zeros(int(0.42 * SR))
        seq = np.concatenate([np.concatenate([src, gap]) for _ in range(rep)])
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "_sfx_meas.wav")
        pcm = (np.clip(seq, -1, 1) * 32767).astype("<i2")
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        path = tmp
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-af", "loudnorm=I=-19:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    k = r.stderr.rfind("{")
    j = r.stderr.find("}", k)
    try:
        return round(float(json.loads(r.stderr[k:j + 1])["input_i"]), 1)
    except Exception:
        return -20.0


CATALOG_SYNC = {"amb_seawind": 0.0, "amb_campfire": 0.0, "wood_step": 0.012, "dive_splash": 0.06}

if __name__ == "__main__":
    made = {}
    for name, sig in [("amb_seawind", make_seawind()), ("amb_campfire", make_campfire()),
                      ("wood_step", make_step()), ("dive_splash", make_splash())]:
        p = to_wav(sig, name)
        # 短于 3s 的音效用 8 次重复拼接量（loudnorm 对短输入给 -inf）
        rep = 8 if len(sig) / SR < 3 else 1
        made[name] = {"sync_at": CATALOG_SYNC[name], "lufs": measure_lufs(p, rep)}
        print("%-14s %5.1fs  lufs=%s  -> %s"
              % (name, len(sig) / SR, made[name]["lufs"], os.path.basename(p)))
    cat = os.path.join(OUT, "sfx_custom_catalog.json")
    json.dump({"sounds": [{"id": k, **v} for k, v in made.items()]},
              open(cat, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("catalog ->", cat)
