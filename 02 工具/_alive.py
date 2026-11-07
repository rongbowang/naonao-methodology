# -*- coding: utf-8 -*-
"""
_alive.py — 画面「活力」体检（2026-10-25 新建）

问题背景
--------
NO.15 的 56~72 秒那 17 秒，画面只有 5 个同心椭圆 + 一个虚线框在晃。
用户原话：「这个画面完全没有什么意义啊，就是几个圈儿放到那儿，啥意思呢」。

但以前没有任何工具能发现这件事：
  _check.mjs    只量元素数 / 文字 / 越界
  _overlap.mjs  只比文字矩形
  _gcheck.mjs   只量图形有没有出画
  __dupcheck.py 只查画面文字和字幕复读
  —— 四个体检全都只看"这一帧对不对"，没有一个看"这十几秒有没有在动"。

这个脚本量的是**运动**：
把画面（裁掉顶部品牌栏和底部字幕区）按每秒 6 帧抽出来，缩成 108x144 灰度，
算相邻帧的平均绝对差。连续多少秒 diff 低于阈值 = 这段时间屏幕是死的。

判据（按 explainroo「Something changes every 2 to 4 seconds」折算）
--------------------------------------------------------------
  静止段 >= 4.0 秒  → **FAIL**（观众会觉得卡住了）
  静止段 2.0~4.0 秒 → WARN
  全片平均 diff     → 低于 1.2 说明整体动作太小（镜头在呼吸但画面没内容）

用法
----
  python _alive.py "每日成果/2026-10-29/NO.15_xxx.mp4"
  python _alive.py --all            # 批量跑 NO.10~NO.17 做横向对比
  python _alive.py <mp4> --json     # 机器可读
"""
import sys
import os
import json
import subprocess
import argparse

import numpy as np

FPS = 6                 # 抽帧率
GW, GH = 108, 144       # 灰度缩略尺寸
CROP = "1080:940:0:180"  # 裁掉顶部品牌栏（0~180）和底部字幕区（1120~1440）
STILL_T = 0.9           # diff 低于这个值算「没动」（0~255 尺度）
FAIL_SEC = 4.0
WARN_SEC = 2.0


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def frames(path):
    """抽出灰度帧，返回 (n, GH, GW) uint8"""
    cmd = ["ffmpeg", "-v", "error", "-i", path,
           "-vf", f"fps={FPS},crop={CROP},scale={GW}:{GH},format=gray",
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (GW * GH)
    return np.frombuffer(raw[:n * GW * GH], dtype=np.uint8).reshape(n, GH, GW)


def analyse(path):
    dur = probe(path)
    fr = frames(path).astype(np.int16)
    if len(fr) < 3:
        return None
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))   # 长度 n-1
    t = (np.arange(len(d)) + 1) / FPS                   # 每段结束时刻

    still = d < STILL_T
    # 找连续静止段
    segs, start = [], None
    for i, s in enumerate(still):
        if s and start is None:
            start = i
        elif not s and start is not None:
            segs.append((start / FPS, (i + 1) / FPS))
            start = None
    if start is not None:
        segs.append((start / FPS, len(still) / FPS))
    segs = [(a, b) for a, b in segs if b - a >= 1.0]
    segs.sort(key=lambda x: x[1] - x[0], reverse=True)

    dead = float(still.mean())
    return {
        "file": os.path.basename(path),
        "dur": round(dur, 1),
        "mean_diff": round(float(d.mean()), 2),
        "median_diff": round(float(np.median(d)), 2),
        "p90_diff": round(float(np.percentile(d, 90)), 2),
        "still_ratio": round(dead, 3),
        "longest_still": round(max((b - a for a, b in segs), default=0), 1),
        "stills": [(round(a, 1), round(b, 1)) for a, b in segs[:8]],
        # 逐 5 秒窗口的平均 diff，用来看「哪十几秒是平的」
        "windows": [
            (round(i * 5, 0), round(float(d[i * FPS * 5:(i + 1) * FPS * 5].mean()), 2))
            for i in range(int(dur // 5))
        ],
    }


def report(r, verbose=True):
    tag = "FAIL" if r["longest_still"] >= FAIL_SEC else (
        "WARN" if r["longest_still"] >= WARN_SEC else "OK  ")
    line = (f"[{tag}] {r['file']}  {r['dur']}s  "
            f"mean={r['mean_diff']}  p90={r['p90_diff']}  "
            f"静止占比={r['still_ratio']*100:.0f}%  "
            f"最长静止={r['longest_still']}s")
    print(line)
    if verbose and r["stills"]:
        print("        死段：" + "  ".join(f"{a}~{b}s({b-a:.1f}s)" for a, b in r["stills"][:6]))
    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", nargs="?")
    ap.add_argument("--all", action="store_true", help="批量跑 每日成果 下所有 NO.0x 成片")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    from _paths import PUB as root   # 归档容器（新旧兼容）
    targets = []
    if a.all:
        import glob
        for p in sorted(glob.glob(os.path.join(root, "2026-*", "NO.*_竖屏.mp4"))):
            no = os.path.basename(p).split("_")[0]
            if no in ("NO.01", "NO.02", "NO.03", "NO.04", "NO.05", "NO.06",
                      "NO.07", "NO.08", "NO.09"):
                continue   # 旧规格，跳过
            targets.append(p)
    elif a.mp4:
        targets = [a.mp4]
    else:
        ap.error("给一个 mp4，或者 --all")

    res = []
    for p in targets:
        if not os.path.exists(p):
            print("缺文件:", p)
            continue
        r = analyse(p)
        if r is None:
            print("读不出:", p)
            continue
        res.append(r)
        if not a.json:
            report(r)

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif len(res) > 1:
        print("\n—— 汇总 ——")
        print(f"平均 diff: {np.mean([r['mean_diff'] for r in res]):.2f}"
              f"   平均最长静止: {np.mean([r['longest_still'] for r in res]):.1f}s")
        bad = [r for r in res if r["longest_still"] >= FAIL_SEC]
        print(f"有 FAIL 段的期数: {len(bad)}/{len(res)}")


if __name__ == "__main__":
    main()
