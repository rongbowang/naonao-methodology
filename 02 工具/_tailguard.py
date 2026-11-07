#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动探测 TAIL_GUARD —— 替代每期手填常数（2026-11-07 新增）

## 为什么要它

`gen_timeline.py` 里原来每期都有一个手填的 `TAIL_GUARD`（11-07 = 0.359、11-14 = 0.260 …），
注释写着「20ms 窗口量 _ALL.wav 句间静音 RMS、取最安静点」。
后果有两个：
1. 每期都要人肉扫一遍静音，算偏一格就切在字上（A02 那类事故的人工环节）；
2. 9 期里 `gen_timeline.py` 出现 **8 个不同版本**，差异全在这一个常数 + 注释，
   哈希校验完全失效，无法判断"哪份是最新版"。

本模块把这一步改成机器算：给定切片长度，在 `_ALL.wav` 的
`[cut_len, cut_len + MAX_GUARD]` 区间里滑 20ms 窗，找出**第一段连续静音**，
取该段的中点作为切片点，返回它相对 `cut_len` 的偏移，即 TAIL_GUARD。

（为什么不用"全局最安静点"：语音之间的静音 RMS 都差不多低，全局最小值常常落在
「下一句起音前 26ms」的边界上 —— 实测 11-14 会算出 0.434，而人工取的是静音段中点
21.838 → 0.260。贴着下一句起音切，就是在赌 TTS 的起音不提前。）

## 命令行

    python _tailguard.py --all "30 制作/<期>/audio/_tmp/_ALL.wav" --len 21.578
    # → TAIL_GUARD = 0.247（静音段 21.623~22.027，中点 21.825）
    #   人工历史值是 0.260（切片点 21.838），差 13ms，都在静音段内、都不切字。

    python _tailguard.py --all ... --len 21.578 --json
    # → {"tail_guard": 0.247, "cut_len": 21.578, "method": "rms-20ms-midpoint"}

## 接进 gen_timeline.py（把这一行换掉即可）

    # 旧：TAIL_GUARD = 0.260        ← 手填，每期不同
    # 新：
    import sys; sys.path.insert(0, r"02 工具 的绝对路径")
    from _tailguard import find_tail_guard
    TAIL_GUARD = find_tail_guard(ALL_WAV, cut_len)

换了以后，各期的 gen_timeline.py 就可以完全一致，常数差异消失。

## 注意

- 只读，不改任何音频、不覆盖任何文件。
- 找不到静音（RMS 一直很高）时返回 MAX_GUARD 并给出 warning，不会静默给 0。
"""

from __future__ import annotations

import argparse
import json
import sys
import wave

import numpy as np

MAX_GUARD = 0.5     # 与 gen_timeline.py 注释里的口径一致
WIN = 0.020         # 20ms 窗
STEP = 0.005        # 5ms 步进
MIN_GUARD = 0.05    # 兜底，别贴到字上
QUIET_RMS = 0.03    # 低于这个算静音（实测：静音 0.002~0.006，尾音 0.088，起音 0.156）


def _read_mono(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(n)

    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 1:
        x = (np.frombuffer(raw, dtype="<u1").astype(np.float64) - 128.0) / 128.0
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"不支持的采样位宽: {width * 8} bit")

    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def find_tail_guard(all_wav: str, cut_len: float, *, max_guard: float = MAX_GUARD) -> float:
    """返回应加的 TAIL_GUARD（秒）。cut_len = 本镜切片长度（timeline 里的 len）。"""
    x, sr = _read_mono(all_wav)
    start = int(round(cut_len * sr))
    stop = min(len(x), int(round((cut_len + max_guard + 0.1) * sr)))
    if stop - start < int(WIN * sr):
        print(f"[warn] 区间太短，退化为 max_guard={max_guard}", file=sys.stderr)
        return max_guard

    seg = x[start:stop]
    w = max(1, int(WIN * sr))
    s = max(1, int(STEP * sr))

    # 逐窗算 RMS，得到 (窗起始样本, rms) 序列
    centers: list[tuple[int, float]] = []
    for i in range(0, max(1, len(seg) - w + 1), s):
        chunk = seg[i:i + w]
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        centers.append((start + i + w // 2, rms))

    # 找第一段连续静音（rms < QUIET_RMS）
    runs: list[tuple[int, int, float]] = []
    run_start = None
    run_end = None
    run_min = float("inf")
    for center, rms in centers:
        if rms < QUIET_RMS:
            if run_start is None:
                run_start = center
                run_min = float("inf")
            run_end = center
            run_min = min(run_min, rms)
        elif run_start is not None:
            runs.append((run_start, run_end, run_min))
            run_start = None
    if run_start is not None:
        runs.append((run_start, run_end, run_min))

    if not runs:
        print(f"[warn] 区间内没有 RMS<{QUIET_RMS} 的静音段，请人工复核 cut_len", file=sys.stderr)
        return max_guard

    a, b, rms_min = runs[0]
    guard = ((a + b) / 2.0 / sr) - cut_len
    guard = min(max(guard, MIN_GUARD), max_guard)

    print(f"[info] 静音段 {(a / sr):.3f}~{(b / sr):.3f}s（RMS 最低 {rms_min:.5f}），取中点 → {cut_len + guard:.3f}",
          file=sys.stderr)
    return round(guard, 3)


def main() -> int:
    ap = argparse.ArgumentParser(description="自动探测 TAIL_GUARD")
    ap.add_argument("--all", required=True, help="audio/_tmp/_ALL.wav 路径")
    ap.add_argument("--len", type=float, required=True, help="本镜切片长度（秒）")
    ap.add_argument("--max-guard", type=float, default=MAX_GUARD)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    g = find_tail_guard(a.all, a.len, max_guard=a.max_guard)
    if a.json:
        print(json.dumps({"tail_guard": g, "cut_len": a.len, "method": "rms-20ms"}, ensure_ascii=False))
    else:
        print(f"TAIL_GUARD = {g:.3f}   (cut_len={a.len:.3f} → 切片点 {a.len + g:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
