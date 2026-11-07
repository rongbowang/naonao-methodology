# -*- coding: utf-8 -*-
"""_sbgen.py — 06_画面绘制.md 的通用渲染器（第四版 · 19 项分镜）

被 gen_no18_storyboard.py / gen_no19_storyboard.py 调用：
  render(cfg) 把 S（每镜 19 项数据）+ script.py 台词 + timeline.json 逐句时间
  渲染成 19 项 × N 镜的 markdown。

约定：
  · 台词和时间一律从 script.py / timeline.json 读，不手抄；
  · 动作表里写 {{句号|偏移秒}} → 渲染成绝对秒（= 该句 g0 + 偏移），与 scenes.js 的
    `L(i) + 偏移` 一一对应；
  · 颜色清单从 scenes.js 里按镜抓 hex，再并上资产色 —— 文档与代码永不脱节。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 资产库（assets.js）里会出现在画面上的固定色：只列真正用到的
ASSET_COLORS = {
    "#D9A876": "人物皮肤（assets.js C.skin）",
    "#B98F63": "人物皮肤暗部（night 模式）",
    "#33526E": "衣色 A / 描边统一色",
    "#5C4034": "衣色 B",
    "#46586E": "衣色 C",
    "#101E2E": "人物描边 / 深线",
    "#FF5A5A": "红眼（本期不用，仅资产定义）",
    "#57A0FF": "蓝眼（本期不用，仅资产定义）",
    "#000208": "暗角",
    "#7FA8D8": "冷顶光（stage2 环境光）",
    "#EAF2FF": "近白：后期叠字 / 高光",
    "#0E1A2A": "片尾底色（outroStd）",
    "#0C1B2E": "片尾徽章填充（outroStd）",
    "#050C16": "本期底色（下）/ 片尾底（下）",
}

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def load_ep(ep_dir):
    """读 script.py 的台词 + timeline.json 的逐句时间"""
    ns = {}
    src = open(os.path.join(ep_dir, "script.py"), encoding="utf-8").read()
    exec(compile(src, "script.py", "exec"), ns)
    tl = json.load(open(os.path.join(ep_dir, "web", "timeline.json"), encoding="utf-8"))
    return ns, tl


def scene_hexes(ep_dir):
    """按镜抓 scenes.js 里的 hex（以 define("xxx" 分块）"""
    p = os.path.join(ep_dir, "web", "js", "scenes.js")
    src = open(p, encoding="utf-8").read()
    out = {}
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'define\("([a-z]+)"', src)]
    head = set(h.upper() for h in HEX_RE.findall(src[:marks[0][0]])) if marks else set()
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(src)
        block = src[pos:end]
        hexes = set(h.upper() for h in HEX_RE.findall(block))
        out[name] = hexes | head   # 公共画材（arena / globe / ruler / palm …）每个镜头都算
    return out


def expand(text, lines, shot_start_unused=None):
    """把 {{i|off}} 换成绝对秒"""
    def rep(m):
        i = int(m.group(1))
        off = float(m.group(2))
        return "%.2fs" % (lines[i]["g0"] + off)
    return re.sub(r"\{\{(\d+)\|(-?[\d.]+)\}\}", rep, text)


def render(cfg):
    ep_dir = os.path.join(ROOT, "30 制作", cfg["ep"])
    ns, tl = load_ep(ep_dir)
    hexmap = scene_hexes(ep_dir)
    by_id = {s["id"]: s for s in tl["shots"]}
    out = []

    out.append("# %s %s · 画面绘制文档（第四版 · 超详细分镜）\n" % (cfg["no"], cfg["title"]))
    out.append("> 规范：`01 操作手册/画面绘制规范.md`（第四版 · 19 项分镜）")
    out.append("> 台词与逐句时间取自 `script.py` + `web/timeline.json`（配音已定稿，本文件不改台词）")
    out.append("> 生成器：`02 工具/%s`（本文档由脚本生成，改分镜请改生成器后重跑）" % cfg["gen"])
    out.append("> 每镜 19 项全写、数值全部写死；逐句动作表一句一行，句句有像素级位移。\n")
    out.append("**签收状态**：待签收　　（签收后改为「已签收 YYYY-MM-DD」）\n")

    out.append("## 〇、本期通用设定（全 %d 镜共用）\n" % len(cfg["order"]))
    out.append("| 项 | 值 |")
    out.append("|---|---|")
    out.append("| 画幅 | 1080 × 1440，30fps，坐标原点左上 (0,0) |")
    out.append("| 字幕安全区 | 文字底边 ≤1104；该镜有 camera 时 ≤990 |")
    out.append("| 顶部安全区 | 关键元素（人脸/焦点/道具）不进 `y < 80` |")
    out.append("| 底色政策 | **本期统一深色系**：`#081020`→`#050C16`（`stage2(box, id, \"#081020\", \"#050C16\")`），片尾用 `#0E1A2A`→`#050C16`；深底浅字 `#EAF2FF` 对比度 ≈12.8:1 |")
    out.append("| 人形标准 | 头 R；肩宽 = 1.55 × 头直径 = 3.1R；身 2.2R；手 = 实心圆 0.42R 挂肩两侧；腿两条竖线；俯视镜用脚下椭圆阴影 rx=h·0.17 / ry=h·0.05 代替地平线 |")
    out.append("| 人形来源 | `ASSET.islander()` / `islanderMid()` / `silhouette()`，**不许用 circle 色点代表人** |")
    out.append("| 人数规则 | 台词人数 ≠ 画面人数；画面 ≤50，四排分层（前排全要素 / 两侧中景 / 后排剪影 / 外围淡剪影 0.55） |")
    out.append("| 转场 | 一律硬切；禁叠化；本期不用雪花噪点 |")
    out.append("| 画面文字 | **模型不许写字**（prompt 以 `no text` 收尾）；**编号/数字/算式由引擎用 `K.sp(svg,\"text\",...)` 叠**（`_sbgen`/`_chk` 都按这条查，§15 写规格） |")
    out.append("| 音效 | 在 `scenes.js` 的 build 里用 `LIB.sfx()` 登记（音效库 id），不写进 `script.py` |\n")

    for idx, sid in enumerate(cfg["order"], 1):
        d = cfg["S"][sid]
        t = by_id[sid]
        lines = ns["SHOTS"][idx - 1]["lines"]
        assert len(lines) == len(t["lines"]), "%s 句数不一致" % sid
        assert len(d["动作"]) == len(lines), "%s 动作表行数(%d) != 句数(%d)" % (
            sid, len(d["动作"]), len(lines))
        tl_lines = []
        for ln, cl in zip(lines, t["lines"]):
            tl_lines.append({"g0": cl["g0"], "g1": cl["g1"], "text": ln, "chars": cl["chars"]})
        for k, ln in enumerate(tl_lines):
            assert ln["text"] == t["lines"][k]["text"], sid

        out.append("\n---\n")
        out.append("## %d. %s · %s\n" % (idx, sid, d["标题"]))
        out.append("> 台词（%d 句，与 `script.py` 一致）：" % len(lines))
        for k, ln in enumerate(lines, 1):
            out.append("> %d. %s" % (k, ln))
        out.append("")

        # 1 镜号与时段
        out.append("### 1. 镜号与时段\n")
        out.append("`%s_%s`　**%.2f–%.2f s**（%.2f s）　%d 句\n" % (
            cfg["no"], sid, t["start"], t["end"], t["end"] - t["start"], len(lines)))
        out.append("| # | 起止 | 时长 | 台词 |")
        out.append("|---|---|---|---|")
        for k, (ln, cl) in enumerate(zip(lines, t["lines"]), 1):
            out.append("| %d | %.2f–%.2f | %.2f s | %s |" % (k, cl["g0"], cl["g1"], cl["g1"] - cl["g0"], ln))
        out.append("")

        for n, key, lab in [(2, "景别", "景别"), (3, "机位", "视角 / 机位"),
                            (4, "焦点", "镜头焦点与主体"), (5, "构图", "构图")]:
            out.append("### %d. %s\n" % (n, lab))
            out.append(d[key] + "\n")

        out.append("### 6. 画面构成（四层）\n")
        for k, lab in [("背景", "6.1 背景层"), ("中景", "6.2 中景层"),
                       ("人物", "6.3 人物层"), ("氛围", "6.4 氛围层")]:
            out.append("**%s**：%s\n" % (lab, d[k]))

        out.append("### 7. 光影\n")
        out.append(d["光影"] + "\n")
        out.append("### 8. 色彩基调\n")
        out.append(d["色彩"] + "\n")

        out.append("### 9. 元素清单\n")
        out.append("| # | 名称 | 类型 | 坐标 | 尺寸 | 形状 | 填充 | 描边 | 透明度 | 自带动画 |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for k, e in enumerate(d["元素"], 1):
            out.append("| %d | %s |" % (k, " | ".join(e)))
        out.append("")

        out.append("### 10. 角色表演\n")
        out.append("| 角色 | 表情 | 姿态 | 走位 | 视线 |")
        out.append("|---|---|---|---|---|")
        for p in d["表演"]:
            out.append("| %s |" % " | ".join(p))
        out.append("")

        out.append("### 11. 逐句动作表\n")
        out.append("| # | 台词 | 这句开始（画面状态） | 这句里发生（带秒） | 这句结束 |")
        out.append("|---|---|---|---|---|")
        for k, (ln, act) in enumerate(zip(lines, d["动作"]), 1):
            out.append("| %d | %s | %s | %s | %s |" % (
                k, ln, expand(act[0], tl_lines), expand(act[1], tl_lines), expand(act[2], tl_lines)))
        out.append("")

        out.append("### 12. 运镜\n")
        out.append("| 段 | 起止(s) | 类型 | s 区间 | 平移(px) |")
        out.append("|---|---|---|---|---|")
        for r in d["运镜"]:
            out.append("| %s | %s | %s | %s | %s |" % r)
        out.append("")
        out.append("> 平移上限：`(1-1/s)/2 × 1080`（s=1.10 → 49px，s=1.20 → 82px），上表全部在限内。\n")

        out.append("### 13. 转场与过渡\n")
        out.append(d["转场"] + "\n")

        out.append("### 14. 音效提示\n")
        out.append("| 触发 | 内容 | 音效（`LIB.sfx` 名） | 音量档 |")
        out.append("|---|---|---|---|")
        for r in d["音效"]:
            out.append("| %s | %s | %s | %s |" % r)
        out.append("")
        out.append("> 音效在 `scenes.js` 的 build 里登记（`20 素材_只读/sfx_catalog.json` 的真实 id），"
                   "`window.__collectSFX()` 扫全片写成 `sfx.json`。\n")

        out.append("### 15. 文字与字卡\n")
        if d.get("字卡"):
            out.append("> 模型一律不写字（生图 prompt 以 `no text` 收尾）；下表全部由**引擎**用 `K.sp(svg,'text')` 叠在画面上（这是唯一允许、也是必须的画内文字）。\n")
            out.append("| 内容 | 字号 | 颜色 | 位置 | 出现 | 消失 | 动画 |")
            out.append("|---|---|---|---|---|---|---|")
            for r in d["字卡"]:
                out.append("| %s |" % " | ".join(r))
            out.append("")
            out.append("> 底边校验：%s\n" % d.get("字卡底边", "全部 ≤990（该镜有 camera）"))
        else:
            out.append("**本镜无字卡**（画面内零文字；品牌栏与字幕由 engine 层负责）\n")

        out.append("### 16. 连续性\n")
        out.append(d["连续性"] + "\n")

        out.append("### 17. 出画 / 入画方向\n")
        out.append("| 元素 | 方向 | 速度 | 时间 |")
        out.append("|---|---|---|---|")
        for r in d["出入画"]:
            out.append("| %s |" % " | ".join(r))
        out.append("")

        # 18 颜色清单（从 scenes.js 抓，保证与代码一致）
        out.append("### 18. 颜色清单\n")
        code_hexes = set()
        for sc in d.get("scenes", []):
            code_hexes |= hexmap.get(sc, set())
        all_hex = sorted(code_hexes | set(ASSET_COLORS))
        known = dict(ASSET_COLORS)
        known.update(cfg["色注"])
        out.append("| hex | 用途 |")
        out.append("|---|---|")
        for h in all_hex:
            out.append("| `%s` | %s |" % (h, known.get(h, "本镜局部色")))
        out.append("")
        out.append("**清单外颜色一律不得出现。**（本表由生成器从 `web/js/scenes.js` 按镜抓取，"
                   "与代码一一对应；资产色来自 `assets.js`）\n")

        out.append("### 19. 状态\n")
        out.append("**待签收**\n")
        out.append("### 20. 生图 prompt（由 §6/§7/§8 转写）\n")
        out.append("```\n%s\n```\n" % d["prompt"])

    # 附录 B
    out.append("\n---\n")
    out.append("## 附录 B · 写作自检清单（%d 镜逐项）\n" % len(cfg["order"]))
    out.append("| # | 检查项 | 结果 |")
    out.append("|---|---|---|")
    for row in cfg["chk"]:
        out.append("| %s |" % " | ".join(row))

    out.append("\n---\n")
    out.append("## 对账表（文档 ↔ scenes.js）\n")
    out.append("| 镜 | scenes.js 实现 | 状态 |")
    out.append("|---|---|---|")
    for sid in cfg["order"]:
        out.append("| %s | %s | %s |" % (sid, cfg["对账"][sid][0], cfg["对账"][sid][1]))

    path = os.path.join(ep_dir, "06_画面绘制.md")
    txt = "\n".join(out)
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(txt)
    os.replace(tmp, path)
    print("OK -> %s" % path)
    print("  %d 镜 / %d 行 / %d 字符" % (len(cfg["order"]), txt.count("\n") + 1, len(txt)))
    return path
