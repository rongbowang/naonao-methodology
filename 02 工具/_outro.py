# -*- coding: utf-8 -*-
"""_outro.py — 片尾体检：台词是不是三句版 + 画面有没有真的挂上脑子动画。

背景（2026-10-27 用户点名）：「你至少得把那个我们新做的那个动画给放上去吧。」
以前片尾场景是每期手抄一遍，抄漏 `brainImgPlay` 就变成一个不动的脑子 ——
画面不报错、`_check.mjs` 只数元素、`_alive.py` 只量抖动，全都不管。

四条判据：
  1. 台词三句：恭喜你，第 N 个知识装进脑子了。 / 下一期我们来看：<问句>？ / 关注 脑脑不老佬，明天继续涨脑子。
  2. 预告必须是问句（句尾「？」），且不复述下期开场钩子
  3. scenes.js 里 `define("outro"` 必须存在
  4. 片尾必须调 `brainImgPlay`（或用模板的 `outroStd`），否则脑子不会动

用法：python _outro.py [--from 27] [--to 48]
"""
import os, re, sys

from _paths import proj_dir, list_projects   # 期工程目录（新旧兼容）
TAIL = "关注 脑脑不老佬，明天继续涨脑子。"
PRE = "下一期我们来看："


def clean(t):
    return re.sub("[，。！？；：、…—·「」『』《》（）()\"'.,!?;: \u3000]", "", t)


def bigrams(t):
    t = clean(t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def load(ns_path):
    ns = {}
    exec(compile(open(ns_path, encoding="utf-8").read(), ns_path, "exec"), ns)
    return ns


def main():
    lo, hi = 1, 999   # 默认全范围；旧方向时代硬编码过 27~48
    if "--from" in sys.argv:
        lo = int(sys.argv[sys.argv.index("--from") + 1])
    if "--to" in sys.argv:
        hi = int(sys.argv[sys.argv.index("--to") + 1])

    dirs = {}
    for d in list_projects():
        m = re.match(r"NO\.(\d+)", d)
        if m:
            dirs[int(m.group(1))] = d

    rows, bad = [], 0
    for n in sorted(k for k in dirs if lo <= k <= hi):
        proj = proj_dir(dirs[n])
        sf = os.path.join(proj, "script.py")
        if not os.path.isfile(sf):
            continue
        ns = load(sf)
        shots = ns["SHOTS"]
        outro = None
        for s in reversed(shots):
            if "outro" in s["id"]:
                outro = s
                break
        probs = []
        if outro is None:
            probs.append("没有 outro 镜")
            rows.append((n, "—", "—", "；".join(probs)))
            bad += 1
            continue
        L = outro["lines"]
        teaser = L[1] if len(L) > 1 else ""
        # 1) 三句结构
        if len(L) != 3:
            probs.append("台词 %d 句（应 3 句）" % len(L))
        if not ("恭喜" in L[0] and "装进脑子" in L[0]):
            probs.append("第 1 句不是「恭喜…装进脑子」")
        if not teaser.startswith(PRE):
            probs.append("第 2 句没有「%s」" % PRE)
        elif not teaser.rstrip().endswith("？"):
            probs.append("预告不是问句")
        if L[-1].strip() != TAIL:
            probs.append("第 3 句不是固定尾标")
        # 2) 预告 vs 下期开镜首句：不许复述
        nxt = n + 1
        sim = 0.0
        if nxt in dirs:
            nx = load(os.path.join(proj_dir(dirs[nxt]), "script.py"))
            hook = nx["SHOTS"][0]["lines"][0]
            a, b = bigrams(teaser.replace(PRE, "")), bigrams(hook)
            sim = len(a & b) / max(1, len(a | b))
            if sim >= 0.60:
                probs.append("预告复述下期钩子（%.2f）" % sim)
        # 3) 画面：脑子动画
        sc = os.path.join(proj, "web", "js", "scenes.js")
        has_scene = os.path.isfile(sc)
        brain = "—" if not has_scene else ""
        if has_scene:
            src = open(sc, encoding="utf-8").read()
            if 'define("outro"' not in src:
                probs.append("scenes.js 没有 define(\"outro\")")
                brain = "缺失"
            elif "outroStd" in src:
                brain = "outroStd"
            elif "brainImgPlay" in src and "brainImg" in src:
                brain = "手写"
            else:
                probs.append("片尾没挂 brainImgPlay（脑子不会动）")
                brain = "没动"
        rows.append((n, "%d 句" % len(L), brain, "；".join(probs)))
        if probs:
            bad += 1

    print("%-6s %-6s %-9s %s" % ("期", "台词", "脑子", "问题"))
    print("-" * 76)
    for n, c, b, p in rows:
        print("NO.%02d  %-6s %-9s %s" % (n, c, b, p or "—"))
    print("\n共 %d 期，%d 期有问题" % (len(rows), bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
