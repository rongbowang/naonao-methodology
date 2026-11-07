#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_episode.py — 从源期骨架新建一期，治「每期手抄 web/ 导致 8 个分叉版本」

    python new_episode.py NO.32 2026-11-16 "折纸七次" "一张纸最多能折几次" --from NO.30
    python new_episode.py NO.32 2026-11-16 "折纸七次" "..." --from NO.30 --dry-run

## 拷什么 / 不拷什么

**拷（代码模板，九期应当完全一致）**
    web/*.mjs         _alive_pre _bbox _check _gcheck _overlap _q _shot _subbox capture cover
    web/*.py          build_voice gen_timeline mux
    web/*.html/css    index.html cover.html style.css
    web/js/*.js       assets cover_arts engine kit lib props props_cell props_grid props_story
    期根 *.py         tts_whole tts_resume
    02 工具 *.py      _dupcheck _wcheck _outro（九体检里这三个从来没进过 web）

**不拷（本期数据，必须自己长出来）**
    timeline.json / timeline.js / voice.wav / sfx.json / bgm.json / size.json
    web/js/scenes.js（生成空骨架）、*.mp4、*.log、covers.json、cues.json、assets/

## 生成物
    <期>/script.py          骨架（NO/TITLE/SUBTITLE/COUNTDOWN + 5 镜空 SHOTS）
    <期>/_上下文.md          本期开工上下文包（新会话直接读它，不用翻历史）
    目录骨架：web/ web/js/ web/assets/ audio/shots/ audio/_tmp/ 30_交付/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "30 制作"
TOOLS = ROOT / "02 工具"

COPY_TOP = ["_alive_pre.mjs", "_bbox.mjs", "_check.mjs", "_gcheck.mjs", "_overlap.mjs",
            "_q.mjs", "_shot.mjs", "_subbox.mjs", "build_voice.py", "capture.mjs",
            "cover.html", "cover.mjs", "gen_timeline.py", "index.html", "mux.py", "style.css"]
COPY_JS = ["assets.js", "cover_arts.js", "engine.js", "kit.js", "lib.js", "props.js",
           "props_cell.js", "props_grid.js", "props_story.js"]
COPY_EP = ["tts_whole.py", "tts_resume.py"]
COPY_TOOLS = ["_dupcheck.py", "_wcheck.py", "_outro.py"]

SCRIPT_TPL = '''# -*- coding: utf-8 -*-
"""{no} {title} · 骨架（由 new_episode.py 生成，填写后删掉本行）

顺序不能反：先定 SHOTS 与台词 → 跑 check_style + _humanize → 【送审1】
→ 画面关键帧 → 06_画面绘制.md → 【送审2】 → 配音 → 作画 → 九体检 → 渲染
"""

NO = "{no}"
TITLE = "{title}"
SUBTITLE = "{subtitle}"

# 倒计时：第 N 句说完后画面 3-2-1，台词不念数字
COUNTDOWN = {{"after_shot": "00_open", "beats": 3, "beat_seconds": 1.0,
             "sfx": "boom-hit-soft"}}

# 每镜：id / scene / n（句数）/ lines；scene 取 open do solve end outro
SHOTS = [
    {{"id": "00_open",  "scene": "open",  "n": 0, "lines": []}},
    {{"id": "01_do",    "scene": "do",    "n": 0, "lines": []}},
    {{"id": "02_solve", "scene": "solve", "n": 0, "lines": []}},
    {{"id": "03_end",   "scene": "end",   "n": 0, "lines": []}},
    {{"id": "04_outro", "scene": "outro", "n": 0, "lines": []}},
]
'''

CTX_TPL = '''# {no} {title} · 上下文包

> 新开一个会话做这一期，先读这一页，不要翻历史记录。
> 全局规则在 skill：`00 规格与决策/naonao-production/SKILL.md`（本页只写本期专属信息）。

## 一、本期信息

| 项 | 值 |
|---|---|
| 期号 | {no} |
| 日期 | {date} |
| 标题 | {title} |
| 副标题 | {subtitle} |
| 画幅 | 1920×1080 横屏（安全区文字底边 ≤ 760） |
| 镜数 | 5 镜：00_open / 01_do / 02_solve / 03_end / 04_outro |
| 片尾 | 三句固定，一字不改，由 lib.js `outroStd()` 实现 |

## 二、开工顺序（只有两道人工送审）

1. 写 `script.py` 的 SHOTS → `check_style.py`（硬 FAIL）+ `_humanize.py`（≤4 分）
2. **【送审1】** 文案
3. 画面：先出关键帧预览 `99 归档/_构图预览/noXX_keyframes.html`，再写 `06_画面绘制.md`（每镜 19 项）
4. **【送审2】** 画面文档
5. 配音（`tts_whole.py` → `build_voice.py`）→ 作画（`js/scenes.js`，动作锚写 `L(i)=shot.lines[i].g0-shot.start`）
6. 九体检 → 渲染 → 封面 → 归档

## 三、命令

```powershell
$PY = "C:\\Users\\13071\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe"

# 体检（出 PASS/FAIL 表，别跳）
& $PY "02 工具\\preflight.py" {no}

# 单镜试渲（先看开场镜，别直接全片）
& $PY "02 工具\\render_all.py" {no} --pilot=00_open --par=4

# 全片渲染
& $PY "02 工具\\render_all.py" {no} --par=4
```

## 四、本期进度

- [ ] 剧本 SHOTS
- [ ] 送审1
- [ ] 关键帧预览
- [ ] 06_画面绘制
- [ ] 送审2
- [ ] 配音
- [ ] scenes.js
- [ ] 九体检
- [ ] 渲染
- [ ] 封面与归档

## 五、坑（本期必看）

- 改过 `scenes.js` 再渲，**先挪走 `web/_seg/`**，否则断点续跑拿旧段合出旧画面还报成功。
- `.mjs` 体检脚本在 `web/`，`_dupcheck/_wcheck/_outro` 在 `02 工具/`，两边都要有。
- 字幕是 HTML div，别塞进 `<svg>`（不显示也不报错）。
'''

SCENES_STUB = '''// {no} {title} · 场景脚本骨架
// 每镜一个 build 函数；动作锚写 L(i) = shot.lines[i].g0 - shot.start
// 开工前先读 references/画面生动性.md（每句至少一个 A/B 级动作）
'''


def find_ep(arg: str):
    if not PROD.is_dir():
        return None
    for d in sorted(PROD.iterdir()):
        if not d.is_dir():
            continue
        sp = d / "script.py"
        if sp.exists():
            try:
                m = re.search(r'^NO\s*=\s*["\'](NO\.\d+)["\']',
                              sp.read_text(encoding="utf-8"), re.M)
                if m and m.group(1) == arg:
                    return d
            except Exception:
                pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("no")
    ap.add_argument("date")
    ap.add_argument("title")
    ap.add_argument("subtitle", nargs="?", default="")
    ap.add_argument("--from", dest="src_no", default=None, help="源期 NO.xx（默认取最新一期）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = find_ep(a.src_no) if a.src_no else None
    if src is None:
        eps = sorted([d for d in PROD.iterdir() if d.is_dir() and (d / "script.py").exists()])
        if not eps:
            print("!! 30 制作 下没有可作模板的期")
            return 2
        src = eps[-1]
        if a.src_no:
            print(f"!! 找不到源期 {a.src_no}，退回最新一期 {src.name}")

    dest = PROD / f"{a.date}_{a.title}"
    if dest.exists():
        print(f"!! 目标目录已存在，拒绝覆盖：{dest}")
        return 2

    src_web = src / "web"

    def locate(name, sub=""):
        """逐文件回退：源期 web → 02 工具 → 任一其他期的 web。
        源期自己可能就缺（11-14 就缺 _gcheck/_q/_shot），照它抄会把缺口传下去。
        """
        p = (src_web / sub / name) if sub else (src_web / name)
        if p.exists():
            return p
        if (TOOLS / name).exists():
            return TOOLS / name
        for d in sorted(PROD.iterdir()):
            if not d.is_dir() or d == src:
                continue
            q = (d / "web" / sub / name) if sub else (d / "web" / name)
            if q.exists():
                return q
        return None

    plan = []
    for n in COPY_TOP:
        p = locate(n)
        if p:
            plan.append((p, dest / "web" / n))
        else:
            print(f"  ! 全项目找不到 {n}，跳过")
    for n in COPY_JS:
        p = locate(n, "js")
        if p:
            plan.append((p, dest / "web" / "js" / n))
        else:
            print(f"  ! 全项目找不到 js/{n}，跳过")
    for n in COPY_EP:
        if (src / n).exists():
            plan.append((src / n, dest / n))
    for n in COPY_TOOLS:
        if (TOOLS / n).exists():
            plan.append((TOOLS / n, dest / "web" / n))

    print("=" * 64)
    print(f"新建：{dest.name}   模板来源：{src.name}")
    print(f"  拷代码 {len(plan)} 个文件")
    if a.dry_run:
        for s, d in plan:
            print(f"    {s.relative_to(ROOT)}  →  {d.relative_to(dest)}")
        print("  （--dry-run：未落盘）")
        return 0

    for sub in ("web", "web/js", "web/assets", "audio/shots", "audio/_tmp", "30_交付"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    for s, d in plan:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    (dest / "script.py").write_text(
        SCRIPT_TPL.format(no=a.no, title=a.title, subtitle=a.subtitle), encoding="utf-8")
    (dest / "web" / "js" / "scenes.js").write_text(
        SCENES_STUB.format(no=a.no, title=a.title), encoding="utf-8")
    (dest / "_上下文.md").write_text(
        CTX_TPL.format(no=a.no, date=a.date, title=a.title, subtitle=a.subtitle or "（待定）"),
        encoding="utf-8")

    print(f"\n✓ 已建 {dest}")
    print(f"  web 代码 {len(plan)} 个 / script.py 骨架 / web/js/scenes.js 空骨架 / _上下文.md")
    print(f"\n下一步：\n  1. 填 script.py 的 SHOTS")
    print(f"  2. & $PY \"02 工具\\check_style.py\" \"{dest.relative_to(ROOT)}\\script.py\"")
    print(f"  3. 读 {dest.relative_to(ROOT)}\\_上下文.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
