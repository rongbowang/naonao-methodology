# -*- coding: utf-8 -*-
"""
_deadshot.py — 把「死段」直接对齐到镜头，回答「这一期该改哪几镜」

`_alive.py` 告诉你「哪几秒在死」，这个告诉你「那几秒是哪一镜、台词是什么」。
改画面的时候，直接照着名单改，不用再翻 timeline.json 对时间。

用法：
  python _deadshot.py v17_sloth
  python _deadshot.py --all              # 批量，按死段总长排序
  python _deadshot.py v15_barnum --file web/final.mp4   # 指定片子

输出每镜一行：镜头 id / 时长 / 活动率 / 最长静止 / 台词首句
活动率 = 该镜内 diff ≥ 阈值的帧占比。**低于 35% 的镜头基本就是"静态插图"。**
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _alive import probe, frames, STILL_T, FPS   # 复用同一套抽帧与判据

from _paths import WORK as ENG   # 期工程容器（30 制作 / 工程文件 兼容）


def analyse(proj, mp4=None):
    web = os.path.join(ENG, proj, "web")
    tl_path = os.path.join(web, "timeline.json")
    if not os.path.exists(tl_path):
        return None
    tl = json.load(open(tl_path, encoding="utf-8"))
    mp4 = mp4 or os.path.join(web, "final.mp4")
    if not os.path.exists(mp4):
        return None

    fr = frames(mp4).astype(np.int16)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    ts = (np.arange(len(d)) + 1) / FPS          # 每段结束时刻

    rows = []
    for sh in tl["shots"]:
        a, b, sid = sh["start"], sh["end"], sh["id"]
        m = (ts >= a) & (ts < b)
        seg = d[m]
        if len(seg) == 0:
            continue
        live = float((seg >= STILL_T).mean())
        # 该镜内最长的连续静止
        still = seg < STILL_T
        best = cur = 0
        for s in still:
            cur = cur + 1 if s else 0
            best = max(best, cur)
        first = sh["lines"][0]["text"][:26] if sh.get("lines") else ""
        rows.append({
            "shot": sid, "a": round(a, 1), "b": round(b, 1),
            "dur": round(b - a, 1),
            "live": round(live, 2),
            "dead": round((1 - live) * (b - a), 1),
            "still": round(best / FPS, 1),
            "line": first,
        })
    return {"proj": proj, "total": round(tl["duration"], 1),
            "mean": round(float(d.mean()), 2), "rows": rows}


def show(r):
    print(f"\n{r['proj']}  {r['total']}s  mean={r['mean']}    "
          f"（活动率 <35% 的镜头 = 静态插图）")
    print(f"  {'镜头':<14}{'区间':<16}{'秒':>5}{'活动率':>8}{'死时长':>8}{'最长静止':>9}  台词")
    for x in sorted(r["rows"], key=lambda z: z["live"]):
        flag = "  ← 改" if x["live"] < 0.35 else ("  · " if x["live"] < 0.55 else "")
        print(f"  {x['shot']:<14}{x['a']:>6.1f}~{x['b']:<8.1f}{x['dur']:>5.1f}"
              f"{x['live']*100:>7.0f}%{x['dead']:>8.1f}{x['still']:>8.1f}s  {x['line']}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proj", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--file")
    a = ap.parse_args()

    projs = []
    if a.all:
        # 只取 10-26 起还没按新标准改过的期
        for p in ("v12_wrinkle", "v13_bystander", "v14_millikan",
                  "v16_mercury", "v17_sloth"):
            projs.append(p)
    elif a.proj:
        projs = [a.proj]
    else:
        ap.error("给一个工程名，或者 --all")

    out = []
    for p in projs:
        r = analyse(p, a.file)
        if r is None:
            print("跳过（缺 timeline 或 final.mp4）:", p)
            continue
        out.append(r)
        show(r)

    if len(out) > 1:
        print("\n=== 汇总：按「总死时长」排序 ===")
        for r in sorted(out, key=lambda z: -sum(x["dead"] for x in z["rows"])):
            dead = sum(x["dead"] for x in r["rows"])
            worst = min(r["rows"], key=lambda z: z["live"])
            print(f"  {r['proj']:<16} 总死 {dead:>6.1f}s  "
                  f"最差镜 {worst['shot']}（活动率 {worst['live']*100:.0f}%，"
                  f"最长静止 {worst['still']}s）")


if __name__ == "__main__":
    main()
