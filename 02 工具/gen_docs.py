# -*- coding: utf-8 -*-
"""gen_docs.py — 给每一期生成两份人读文档（ADR-0006）

  05_剧本.md        台词逐句 + 每句起止秒（从 script.py + timeline.json）
  06_画面绘制.md    逐镜七项：时间 / 台词 / 画面 / 元素 / 动效锚点 / 运镜 / 转场

为什么要有它
------------
画面是代码直接生成的，中间没有产物给人看。结果是「渲完 13 分钟才发现画错了」。
这份文档就是那个中间产物：写清楚怎么画，用户签收了才许配音。

数据来源
--------
  script.py          台词、画面（view）、运镜（cam）、生图 prompt（ai）
  web/timeline.json  每镜起止、每句 g0/g1（配音实测，不是估的）
  DRAW（本文件）     元素清单 + 动效锚点 —— 这部分必须人写，机器猜不出来

用法
----
  python gen_docs.py                 # 30 制作 下全部
  python gen_docs.py NO.21_两扇门     # 单期
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
PROD = os.path.join(ROOT, "30 制作")
SKIP_PROJ = set()   # 2026-11-01 起 NO.17 也纳入新流程（补文档 + 重画）

PUNCT = "，。！？；：、…—·「」『』《》（）()\"'.,!?;: \u3000"
LIMIT = 12          # 一口气上限（ADR-0005）


def clean(t):
    return re.sub("[" + PUNCT + "]", "", t)


from drawspec import DRAW   # 画面设计数据（人写）见 drawspec.py


def load(proj):
    p = os.path.join(PROD, proj, "script.py")
    ns = {}
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    tl = None
    tp = os.path.join(PROD, proj, "web", "timeline.json")
    if os.path.exists(tp):
        tl = json.load(open(tp, encoding="utf-8"))
    return ns, tl


def fmt_t(sec):
    return "%.2f" % sec


def write_script_md(proj, ns, tl):
    out = ["# %s · %s（%s）· 剧本\n" % (ns["NO"], ns["TITLE"], ns.get("SUBTITLE", "")),
           "> 机器读 `script.py`，这份是给人读的。台词要改就改 script.py，再重跑本脚本。\n",
           "**一句话**：%s\n" % ns["BAODIAN"],
           "**封面大字**：%s\n" % ns.get("COVER", "")]
    ts = ns.get("TITLES") or []
    if ts:
        out.append("**标题候选**：")
        for i, t in enumerate(ts, 1):
            out.append("%d. %s" % (i, t))
        out.append("")
    tmap = {}
    if tl:
        for s in tl["shots"]:
            tmap[s["id"]] = s
    n = 0
    for s in ns["SHOTS"]:
        t = tmap.get(s["id"])
        head = "## %s" % s["id"]
        if t:
            head += "　%.2f – %.2f 秒（%.1f 秒）" % (t["start"], t["end"], t["end"] - t["start"])
        out.append("\n" + head + "\n")
        cues = (t or {}).get("lines") or []
        for i, ln in enumerate(s["lines"]):
            n += 1
            if i < len(cues):
                out.append("%d. （%.2f–%.2f）%s  " % (n, cues[i]["g0"], cues[i]["g1"], ln))
            else:
                out.append("%d. %s  " % (n, ln))
    out.append("\n共 %d 句。\n" % n)
    open(os.path.join(PROD, proj, "05_剧本.md"), "w", encoding="utf-8").write("\n".join(out))


def write_draw_md(proj, ns, tl, spec):
    no = ns["NO"]
    out = ["# %s · %s · 画面绘制文档\n" % (no, ns["TITLE"]),
           "> 按 `01 操作手册/画面绘制规范.md`（第二版）写。**这份签收之后才允许配音，也才允许开画。**\n",
           "**签收状态**：待签收　　（签收后把这行改成「已签收 YYYY-MM-DD」）\n",
           "## 五条硬约束（每期照抄）\n",
           "1. **人必须画成人形**：头 + 肩（肩宽 = 1.55 × 头直径）+ 身 + 实心圆的手 + 地平线。"
           "不许用颜色点代替人。",
           "2. **每句话都要有动作**：大块位移 / 大块变化 / 进出场。透明度淡入、呼吸、细线移动都不算。",
           "3. **模型不许写字**：prompt 以 `no text` 收尾；编号与字卡后期叠。",
           "4. 文字底边 **≤1104**；该镜有 camera 时只排到 **≤990**；人不许压字幕区。",
           "5. 底色全片统一 `#FFFFFF → #E8F0F8`；转场一律硬切。\n",
           "**人形模板**：头 R=26；肩宽 80（=1.55×52）；身高约 160；手 半径 11 实心圆，挂肩两侧；"
           "地平线 y=980（该镜有 camera 时 y=930）。\n"]
    tmap = {}
    if tl:
        for s2 in tl["shots"]:
            tmap[s2["id"]] = s2
    warn = []
    for s2 in ns["SHOTS"]:
        t = tmap.get(s2["id"])
        d = spec.get(s2["id"], {})
        out.append("\n---\n")
        out.append("## %s" % s2["id"])
        if t:
            dur = t["end"] - t["start"]
            out.append("**%.2f – %.2f 秒**，%d 句，%.1f 秒\n"
                       % (t["start"], t["end"], len(s2["lines"]), dur))
            if dur > 12:
                out.append("> ⚠ **长镜（%.0f 秒）**：逐句动作里至少要有 2 处整屏级变化"
                           "（换背景块 / 换构图 / 主体换位）。\n" % dur)
        else:
            out.append("**（未生成时间轴）**\n")

        out.append("**人物**：%s\n" % d.get("人物", "（待补）"))
        if d.get("道具"):
            out.append("**道具**：")
            for e in d["道具"]:
                out.append("- %s" % e)
            out.append("")

        out.append("**逐句动作**（一句一行，不许空）：\n")
        out.append("| # | 起止 | 台词 | 动作 |")
        out.append("|---|---|---|---|")
        acts = d.get("句动") or []
        if len(acts) != len(s2["lines"]):
            warn.append("%s 句动 %d 条 / 台词 %d 句" % (s2["id"], len(acts), len(s2["lines"])))
        cues = (t or {}).get("lines") or []
        for k, ln in enumerate(s2["lines"]):
            span = ("%.2f–%.2f" % (cues[k]["g0"], cues[k]["g1"])) if k < len(cues) else "—"
            act = acts[k] if k < len(acts) else "（待补）"
            out.append("| %d | %s | %s | %s |" % (k + 1, span, ln.replace("|", "／"), act))
        out.append("")

        if s2.get("cam"):
            out.append("**运镜**：%s\n" % s2["cam"])
        if s2.get("ai"):
            out.append("**生图 prompt**：`%s`\n" % s2["ai"])
        out.append("**转场**：硬切\n")
        out.append("**状态**：待签收\n")
    for w in warn:
        print("  [句动数量对不上] " + w)
    text = "\n".join(out).replace("%%", "%")
    open(os.path.join(PROD, proj, "06_画面绘制.md"), "w", encoding="utf-8").write(text)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name in sorted(os.listdir(PROD)):
        p = os.path.join(PROD, name)
        if not os.path.isdir(p):
            continue
        if only and name != only:
            continue
        if name in SKIP_PROJ:
            continue
        if not os.path.exists(os.path.join(p, "script.py")):
            continue
        ns, tl = load(name)
        write_script_md(name, ns, tl)
        write_draw_md(name, ns, tl, DRAW.get(ns["NO"], {}))
        print("写好了 %s：05_剧本.md / 06_画面绘制.md" % name)


if __name__ == "__main__":
    main()
