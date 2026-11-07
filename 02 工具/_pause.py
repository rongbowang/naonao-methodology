# -*- coding: utf-8 -*-
"""_pause.py — 断句校验（2026-11-01 新建）

为什么要有它
------------
用户原话：
  「这已经是第二次出现『改句子时顺手把逗号删了』（NO.20 19 句、NO.22 24 句、NO.23 5 句……
   同一模式反复出现）。建议在 script.py 里加一道断句校验：检测每句台词字数，
   超过 12 字却没有逗号 / 破折号的句子，自动标红提醒。」

根因：`check_style.py` 有一条 CHOP_RUN（连续 6 个 5~10 字的逗号级小句 = 匀速，判 FAIL）。
它的建议改法有两种 ——「去掉逗号合成 ≥11 字」或「塞 ≤4 字碎片」。
手上一直在用第一种，于是逗号被一次次删掉，句子越写越长，口播换不上气。
**本脚本专门盯这个副作用**：凡是逗号级小句超过 12 字的，一律报出来。

★ 本脚本是**唯一硬门槛**（ADR-0005）。check_style 的 sd / 连续匀速已降为参考分，
  不允许为了它删逗号合成长句。先过这里，再看参考分。

判据
----
  一口气（两个标点之间）超过 12 字 -> 报
  超过 16 字 -> 标「重」，念到一半必须换气，必改

用法
----
  python _pause.py 30 制作/2026-11-06_少了一格/script.py
  python _pause.py --all              # 扫 30 制作 下所有期
退出码 0 = 没有超长小句；1 = 有
"""
import argparse
import glob
import os
import re
import sys

PUNCT = "，。！？；：、…—·「」『』《》（）()\"'.,!?;: \u3000"

# 已发布成片，台词不再动 -> 免检（见 ADR-0005）
SKIP = {"NO.17"}
LIMIT = 12      # 一口气上限
HEAVY = 16      # 必改线


def clean(t):
    return re.sub("[" + PUNCT + "]", "", t)


def check(path):
    ns = {}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)
    shots = ns.get("SHOTS") or []
    no = ns.get("NO", os.path.basename(os.path.dirname(path)))
    if no in SKIP:
        return no, 0, None
    hits = []
    n = 0
    for s in shots:
        for ln in s["lines"]:
            n += 1
            for u in re.split("[" + PUNCT + "]+", ln):
                u = clean(u)
                if len(u) > LIMIT:
                    hits.append((n, s["id"], len(u), u, ln))
    return no, n, hits


def report(path):
    no, n, hits = check(path)
    if hits is None:
        print("%s  已发布成片，免检" % no)
        return 0
    if not hits:
        print("%s  共 %d 句  断句 OK（没有超过 %d 字的一口气）" % (no, n, LIMIT))
        return 0
    print("%s  共 %d 句  发现 %d 处一口气过长：" % (no, n, len(hits)))
    for idx, sid, L, u, ln in hits:
        tag = "【重·必改】" if L > HEAVY else "【建议断】"
        print("  %s 第 %d 句（%s）%d 字：%s" % (tag, idx, sid, L, u))
        print("      原句：%s" % ln)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="script.py 路径")
    ap.add_argument("--all", action="store_true", help="扫 30 制作 下全部")
    a = ap.parse_args()
    if a.all:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "30 制作")
        files = sorted(glob.glob(os.path.join(base, "*", "script.py")))
        rc = 0
        for f in files:
            rc |= report(f)
        return rc
    if not a.path:
        ap.error("要给一个 script.py 路径，或者用 --all")
    return report(a.path)


if __name__ == "__main__":
    sys.exit(main())
