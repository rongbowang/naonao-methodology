# -*- coding: utf-8 -*-
"""_chk_js_colors.py — 文档 §18 与 scenes.js 的色板互查（第 3 项 / 第 9 项的代码侧）

用法：python "02 工具/_chk_js_colors.py"

对每一期：
  · 逐个 define("scene") 抽出代码里写死的 hex
  · 必须 ⊆ 该镜 §18 清单 ∪ assets.js/engine 内置色
  · 同时报告 §18 有、代码没用的色（仅提示，不算错）
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# assets.js / lib.js / kit.js 内置（不算场景自选色）
ALLOW = {
    "#33526E", "#5C4034", "#46586E", "#101E2E", "#B98F63", "#D9A876",
    "#FF5A5A", "#57A0FF", "#4E86B8", "#BFE0FF", "#DCEBFF", "#8FC6FF",
    "#FFE7B0", "#000208", "#050A12", "#A8BED4", "#000000", "#FFFFFF",
    "#FF9440", "#FFC75E", "#FFF6DC", "#0E1A2A", "#050C16", "#0C1B2E",
    "#FFD166", "#081020", "#16304C", "#0F2233", "#1C3A52", "#C0537D",
    "#FDDAE6", "#F2A2BE", "#D4789A", "#E893B1", "#2A1220", "#5E2430",
}
HEXRE = re.compile(r"#[0-9A-Fa-f]{6}")


def shot_sec18(md, sid):
    m = re.search(r"\n## \d+\. " + re.escape(sid) + r" · .*?\n", md)
    if not m:
        return set()
    body = md[m.end():]
    nxt = body.find("\n## ")
    if nxt > 0:
        body = body[:nxt]
    sec = re.search(r"### 18\. 颜色清单\n(.*?)\n", body, re.S)
    return set(h.upper() for h in HEXRE.findall(sec.group(1))) if sec else set()


def check(ep):
    doc = open(os.path.join(ROOT, "30 制作", ep, "06_画面绘制.md"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "30 制作", ep, "web", "js", "scenes.js"), encoding="utf-8").read()
    tl = json.load(open(os.path.join(ROOT, "30 制作", ep, "web", "timeline.json"), encoding="utf-8"))
    blocks = re.split(r'\ndefine\("', js)
    scene = {}
    for b in blocks[1:]:
        scene[b.split('"')[0]] = b
    bad, note = [], []
    for t in tl["shots"]:
        sc = t["scene"]
        if sc not in scene:
            bad.append("scenes.js 缺 define(\"%s\")" % sc)
            continue
        listed = shot_sec18(doc, t["id"])
        used = set(h.upper() for h in HEXRE.findall(scene[sc]))
        miss = sorted(used - listed - ALLOW)
        if miss:
            bad.append("%s(%s) 用了 §18 未列色：%s" % (t["id"], sc, " ".join(miss)))
        unused = sorted(listed - used - ALLOW)
        if unused:
            note.append("%s 的 §18 有 %d 个色代码未用（可能只在文字里描述）：%s" % (
                t["id"], len(unused), " ".join(unused[:8])))
    print("=" * 60)
    print("色板互查：%s" % ep)
    for n in note:
        print("  [note] " + n)
    if bad:
        print("  ❌ %d 项：" % len(bad))
        for b in bad:
            print("     - " + b)
    else:
        print("  ✅ scenes.js 每一镜用到的颜色都在该镜 §18 清单内")
    return len(bad)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    eps = sys.argv[1:] or ["NO.22_少了一格", "NO.23_蒙眼分硬币"]
    n = 0
    for ep in eps:
        n += check(ep)
    sys.exit(1 if n else 0)
