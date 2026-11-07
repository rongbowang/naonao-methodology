# -*- coding: utf-8 -*-
"""_chkdoc.py — 06_画面绘制.md 的自动体检（8 项）

用法：python "02 工具/_chkdoc.py" "30 制作/2026-11-02_围一圈报数"
输出：逐条 PASS/FAIL，最后一行 TOTAL；有 FAIL 时退出码 1。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BAN = ["中间", "旁边", "适当", "大概", "差不多"]
ITEM_KEYS = ["### %d." % i for i in range(1, 20)]


def load(ep_dir):
    doc = open(os.path.join(ep_dir, "06_画面绘制.md"), encoding="utf-8").read()
    tl = json.load(open(os.path.join(ep_dir, "web", "timeline.json"), encoding="utf-8"))
    # 台词（用来在含糊词检查里剔除台词本身）
    ns = {}
    exec(compile(open(os.path.join(ep_dir, "script.py"), encoding="utf-8").read(), "s", "exec"), ns)
    lines = [l for s in ns["SHOTS"] for l in s["lines"]]
    return doc, tl, lines


def sections(doc):
    """按「## n. 镜名 · 标题」切分"""
    idx = [(m.start(), m.group(1)) for m in re.finditer(r"\n## \d+\. ([0-9a-z_]+) · ", doc)]
    out = []
    for i, (pos, sid) in enumerate(idx):
        end = idx[i + 1][0] if i + 1 < len(idx) else doc.find("\n## 附录 B")
        out.append((sid, doc[pos:end]))
    return out


def strip_lines(text, lines):
    """去掉台词原文（台词里允许出现含糊词）"""
    for ln in lines:
        text = text.replace(ln, "")
    return text


def main(ep_dir):
    doc, tl, lines = load(ep_dir)
    secs = sections(doc)
    fails = []
    print("== %s ：%d 镜" % (os.path.basename(ep_dir), len(secs)))

    # 1 19 项 × 7 镜
    ok = True
    for sid, body in secs:
        for k in ITEM_KEYS:
            if body.count(k) != 1:
                fails.append("1/%s 缺或少「%s」" % (sid, k))
                ok = False
    print("1) 19 项齐全            : %s（%d 镜 × 19 项）" % ("PASS" if ok else "FAIL", len(secs)))

    # 2 动作表行数
    ok, tot = True, 0
    for (sid, body), shot in zip(secs, tl["shots"]):
        blk = body[body.index("### 11. 逐句动作表"):body.index("### 12. 运镜")]
        rows = [r for r in blk.split("\n") if re.match(r"^\| \d+ \|", r)]
        tot += len(rows)
        if len(rows) != len(shot["lines"]):
            fails.append("2/%s 动作表 %d 行 != %d 句" % (sid, len(rows), len(shot["lines"])))
            ok = False
    print("2) 逐句动作表行数      : %s（共 %d 行）" % ("PASS" if ok else "FAIL", tot))

    # 3 颜色：文档里出现的 hex 必须在 §18 清单里
    ok = True
    for sid, body in secs:
        blk = body[body.index("### 18. 颜色清单"):body.index("### 19. 状态")]
        listed = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", blk))
        before = body[:body.index("### 18. 颜色清单")]
        used = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", before))
        extra = used - listed
        if extra:
            fails.append("3/%s 清单外颜色 %s" % (sid, sorted(extra)))
            ok = False
    print("3) 颜色清单闭合        : %s" % ("PASS" if ok else "FAIL"))

    # 4 prompt 检查
    ok = True
    for sid, body in secs:
        m = re.search(r"### 20\. 生图 prompt[^\n]*\n\n```\n(.*?)\n```", body, re.S)
        if not m:
            fails.append("4/%s 缺 prompt" % sid); ok = False; continue
        p = m.group(1)
        if not p.strip().endswith("no text"):
            fails.append("4/%s prompt 未以 no text 收尾" % sid); ok = False
        body_wo = p.strip()[:-len("no text")]
        for w in ("number", "numbered", "letter", "text"):
            if re.search(r"\b%s\b" % w, body_wo, re.I):
                fails.append("4/%s prompt 出现 %s" % (sid, w)); ok = False
    print("4) prompt 无文字       : %s" % ("PASS" if ok else "FAIL"))

    # 5 元素清单坐标在 0–1080 × 0–1440
    ok = True
    for sid, body in secs:
        blk = body[body.index("### 9. 元素清单"):body.index("### 10. 角色表演")]
        for row in blk.split("\n"):
            deliberate = ("有意" in row) or ("出画" in row)
            for x, y in re.findall(r"\((\d+)\s*,\s*(\d+)\)", row):
                x, y = int(x), int(y)
                if not (0 <= x <= 1080 and 0 <= y <= 1440):
                    if deliberate:
                        continue          # 有意出画的元素，文档已声明
                    fails.append("5/%s 坐标越界 (%d,%d)" % (sid, x, y)); ok = False
    print("5) 元素坐标在画内      : %s" % ("PASS" if ok else "FAIL"))

    # 6 字卡底边
    ok = True
    for (sid, body), shot in zip(secs, tl["shots"]):
        blk = body[body.index("### 15. 文字与字卡"):body.index("### 16. 连续性")]
        if "本镜无字卡" in blk:
            continue
        note = body[body.index("### 15. 文字与字卡"):body.index("### 16. 连续性")]
        if "底边" not in note:
            fails.append("6/%s 缺字卡底边校验" % sid); ok = False
        elif "1104" not in note:
            fails.append("6/%s 底边校验未写 1104" % sid); ok = False
    print("6) 字卡底边 ≤1104      : %s" % ("PASS" if ok else "FAIL"))

    # 7 含糊词
    ok = True
    body_all = strip_lines(doc[:doc.find("## 附录 B")], lines)
    for w in BAN:
        if w in body_all:
            ctx = body_all[body_all.index(w) - 30:body_all.index(w) + 30].replace("\n", " ")
            fails.append("7 出现含糊词「%s」：…%s…" % (w, ctx)); ok = False
    print("7) 无「中间/旁边/适当」: %s" % ("PASS" if ok else "FAIL"))

    # 8 与 timeline 对齐
    ok = True
    for (sid, body), shot in zip(secs, tl["shots"]):
        m = re.search(r"\*\*([\d.]+)–([\d.]+) s\*\*（([\d.]+) s）　(\d+) 句", body)
        if not m:
            fails.append("8/%s 镜号行格式不对" % sid); ok = False; continue
        a, b, d, n = float(m.group(1)), float(m.group(2)), float(m.group(3)), int(m.group(4))
        if abs(a - shot["start"]) > 0.02 or abs(b - shot["end"]) > 0.02 or n != len(shot["lines"]):
            fails.append("8/%s 与 timeline 不符 (%s–%s/%d 句)" % (sid, a, b, n)); ok = False
    print("8) 句数/时长对齐       : %s" % ("PASS" if ok else "FAIL"))

    print("----")
    if fails:
        for f in fails[:40]:
            print("  ✗", f)
        print("TOTAL: FAIL (%d)" % len(fails))
        return 1
    print("TOTAL: 8/8 PASS")
    return 0


if __name__ == "__main__":
    ep = sys.argv[1] if len(sys.argv) > 1 else "30 制作/2026-11-02_围一圈报数"
    sys.exit(main(os.path.join(ROOT, ep)))
