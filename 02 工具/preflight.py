#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight.py — 一期开渲前的静态体检，一条命令出 PASS/FAIL 表

    python preflight.py NO.29
    python preflight.py 2026-11-13_皮托悖论
    python preflight.py NO.29 --strict-assets   # 作画前 / 交付前请加 --strict-assets：
                                                # 素材盘点缺章算 FAIL（已交付期仍 WARN，闸门管未来不追溯历史）

## 它查什么（每一条都对应一次踩过的坑）

| 检查 | 坑 |
|---|---|
| 文件齐备 | script.py / timeline.json / js/scenes.js / voice.wav 缺一个就别渲 |
| 画幅 1920×1080 | 旧期是竖屏 1080×1440，timeline 里留着旧值会渲成竖屏 |
| 期号一致 | script.py 的 NO 与 timeline 的 no 不一致 = 串期（A01 类的根） |
| 台词逐句一致 | 改了台词没重建 timeline → 画面新、配音旧（A01） |
| 旧段风险 | scenes.js 比 _seg 新 = 会拿旧分段合出旧画面，还报「成功」 |
| 段完整性 | 期望段数 vs 实际 s*.mp4，缺段就是半成品 |
| 九体检脚本齐备 | `.mjs` 在各期 web、`.py` 在 02 工具，新期常见缺 3 个 |
| Scenes 覆盖 | define() 的键 vs timeline 的 shot.scene，缺一个就是"整镜没画" |
| 素材盘点 | 06 的 `## 素材盘点` 三表 + 表 B 全 ✅ + scenes.js 音效/画材都在库（§5.4；老文档缺章只 WARN，作画/交付前加 `--strict-assets` 缺章算 FAIL） |
| _ALL.wav | build_voice 的产物，缺了说明没跑配音 |
| 已交付 | 40 出版物 下有没有这个期号 |

**注意：本脚本只做静态检查，不实跑九个体检。** 实跑要浏览器、要串行端口，
留给渲染流程本身；这里先把「脚本缺没缺、数据对不对得上」一次说清。

退出码：全部 PASS → 0；有 FAIL → 1。
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "30 制作"
PUB = ROOT / "40 出版物"
TOOLS = ROOT / "02 工具"

WANT_SIZE = (1920, 1080)
NINE = ["_bbox.mjs", "_alive_pre.mjs", "_alive.py", "_check.mjs", "_gcheck.mjs",
        "_overlap.mjs", "_dupcheck.py", "_wcheck.py", "_outro.py"]
SEG_FRAMES = 128

results = []   # (level, 项目, 详情)


def add(level, item, detail=""):
    results.append((level, item, detail))


def find_ep(arg: str):
    """按 NO.xx 或目录名定位期目录。"""
    if not PROD.is_dir():
        return None, None
    for d in sorted(PROD.iterdir()):
        if not d.is_dir():
            continue
        sp = d / "script.py"
        if arg == d.name:
            return d, _read_no(sp)
        if sp.exists():
            try:
                m = re.search(r'^NO\s*=\s*["\'](NO\.\d+)["\']',
                              sp.read_text(encoding="utf-8"), re.M)
                if m and m.group(1) == arg:
                    return d, m.group(1)
            except Exception:
                pass
    return None, None


def _read_no(sp: Path):
    try:
        m = re.search(r'^NO\s*=\s*["\'](NO\.\d+)["\']', sp.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else ""
    except Exception:
        return ""


def read_script(sp: Path):
    """ast 解析 SHOTS，返回 [(id, [line,...])]；失败返回 None。"""
    try:
        tree = ast.parse(sp.read_text(encoding="utf-8"))
    except Exception:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == "SHOTS":
                try:
                    data = ast.literal_eval(node.value)
                except Exception:
                    return None
                return [(s.get("id", ""), list(s.get("lines", []))) for s in data]
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    # argv[1:] 里期号/期目录与开关分开解析（最小改动，不引 argparse）
    _args = sys.argv[1:]
    strict_assets = "--strict-assets" in _args
    _pos = [a for a in _args if not a.startswith("--")]
    ep, no = find_ep(_pos[0])
    if ep is None:
        print(f"!! 找不到这一期：{sys.argv[1]}")
        avail = [d.name for d in PROD.iterdir() if d.is_dir()] if PROD.is_dir() else []
        print("   现有：%s" % "、".join(avail))
        return 2

    web = ep / "web"
    print("=" * 70)
    print(f"体检：{no or '（无期号）'}  {ep.name}")
    print("=" * 70)

    # 1 文件齐备
    need = {"script.py": ep / "script.py",
            "web/timeline.json": web / "timeline.json",
            "web/js/scenes.js": web / "js" / "scenes.js",
            "web/voice.wav": web / "voice.wav"}
    missing = [k for k, p in need.items() if not p.exists()]
    if missing:
        add("FAIL", "文件齐备", "缺：" + "、".join(missing))
    else:
        add("PASS", "文件齐备", "4 件都在")

    # 2 timeline 可读 + 画幅
    tl = None
    if need["web/timeline.json"].exists():
        try:
            tl = json.loads(need["web/timeline.json"].read_text(encoding="utf-8"))
        except Exception as e:
            add("FAIL", "timeline 可解析", str(e)[:80])
    if tl:
        w, h = tl.get("width"), tl.get("height")
        if (w, h) == WANT_SIZE:
            add("PASS", "画幅", f"{w}×{h}")
        else:
            add("FAIL", "画幅", f"{w}×{h}，应为 1920×1080")
        # 期号一致
        tl_no = tl.get("no", "")
        if tl_no == no:
            add("PASS", "期号一致", tl_no)
        else:
            add("FAIL", "期号一致", f"script={no} / timeline={tl_no}（串期）")

    # 3 台词逐句一致
    shots = read_script(ep / "script.py")
    if shots and tl:
        tl_shots = {s.get("id"): s for s in tl.get("shots", [])}
        diffs, checked = [], 0
        for sid, lines in shots:
            ts = tl_shots.get(sid)
            if not ts:
                diffs.append(f"{sid}：timeline 里没有这一镜")
                continue
            tlines = [ln.get("text", "") for ln in ts.get("lines", [])]
            if len(tlines) != len(lines):
                diffs.append(f"{sid}：script {len(lines)} 句 / timeline {len(tlines)} 句")
            for i, (a, b) in enumerate(zip(lines, tlines)):
                checked += 1
                if a != b:
                    diffs.append(f"{sid} 第 {i + 1} 句：\n      script  = {a}\n      timeline= {b}")
        if diffs:
            add("FAIL", "台词一致", f"{len(diffs)} 处不一致（改了台词没重建 timeline → 画面新配音旧）")
            for d in diffs[:6]:
                print(f"      {d}")
            if len(diffs) > 6:
                print(f"      … 另 {len(diffs) - 6} 处")
        else:
            add("PASS", "台词一致", f"{checked} 句全对")
    elif not shots:
        add("WARN", "台词一致", "script.py 的 SHOTS 读不出来（非字面量？）")

    # 4 旧段风险
    seg_dir = web / "_seg"
    scenes_p = need["web/js/scenes.js"]
    if seg_dir.is_dir() and scenes_p.exists():
        segs = sorted(seg_dir.glob("s*.mp4"), key=lambda p: p.stat().st_mtime)
        if segs:
            newest_seg = segs[-1].stat().st_mtime
            scenes_mt = scenes_p.stat().st_mtime
            if scenes_mt > newest_seg:
                add("FAIL", "旧段风险",
                    "scenes.js 比 _seg 新 → 会把旧画面合出来还报成功；先挪走 _seg 再渲")
            else:
                add("PASS", "旧段风险", "scenes.js 不新于分段")
    # 5 段完整性（已交付的期不要求分段齐全：渲染完清掉分段属正常）
    date = ep.name[:10]
    pub_ok = False
    day = PUB / date
    if day.is_dir():
        for sub in day.iterdir():
            if no and no in sub.name:
                pub_ok = True
                break
    if tl:
        frames = round(tl["duration"] * 30)
        want_n = (frames + SEG_FRAMES - 1) // SEG_FRAMES
        have_n = len(list(seg_dir.glob("s*.mp4"))) if seg_dir.is_dir() else 0
        if have_n >= want_n:
            add("PASS", "段完整性", f"{have_n} 段齐")
        elif pub_ok:
            add("PASS", "段完整性", f"{have_n}/{want_n} 段；已交付，缺的属正常清理")
        elif have_n == 0:
            add("WARN", "段完整性", f"还没有分段（需要 {want_n} 段）")
        else:
            add("WARN", "段完整性", f"{have_n}/{want_n} 段，缺 {want_n - have_n} 段")

    # 6 九体检脚本：本期 web → 02 工具 → 任一期 web（能拷就算"有"，只是要补）
    in_web, need_copy, gone = [], [], []
    others = [d for d in PROD.iterdir() if d.is_dir() and d != ep] if PROD.is_dir() else []
    for n in NINE:
        if (web / n).exists():
            in_web.append(n)
        elif (TOOLS / n).exists():
            need_copy.append((n, "02 工具"))
        else:
            src = next((d for d in others if (d / "web" / n).exists()), None)
            if src:
                need_copy.append((n, src.name))
            else:
                gone.append(n)
    if gone:
        add("FAIL", "九体检脚本", f"全项目都找不到：{'、'.join(gone)}")
    elif need_copy:
        detail = "；".join(f"{n}←{s}" for n, s in need_copy)
        add("WARN", "九体检脚本", f"本期 web 自带 {len(in_web)}/9，需补 {len(need_copy)}：{detail}")
    else:
        add("PASS", "九体检脚本", "9 个都在本期 web")

    # 7 Scenes 覆盖：作画写没写（缺键 → mountScene 里 Scenes[x] undefined，渲到那一镜必崩）
    scenes_js = need["web/js/scenes.js"]
    if scenes_js.exists() and tl:
        stxt = scenes_js.read_text(encoding="utf-8")
        keys = set(re.findall(r'define\s*\(\s*"([a-z]+)"', stxt))
        want = {s.get("scene") for s in tl.get("shots", []) if s.get("scene")}
        miss = want - keys
        if miss:
            add("FAIL", "Scenes 覆盖",
                f"scenes.js 没定义 {sorted(miss)} → 渲到那一镜必崩（不是元素写错，是整镜没画）")
        else:
            add("PASS", "Scenes 覆盖", f"{len(keys)} 个场景键覆盖 timeline 的 {len(want)} 个")

    # 7.5 素材盘点（SKILL v2.2.0 §5.4 / 工具清单「_assetcheck.py 契约」六条判据，不复制逻辑）
    # 缺章分级（工具清单）：默认 WARN；--strict-assets 算 FAIL —— 但已交付期（web/final.mp4 在）
    # 仍按 WARN，闸门管未来、不追溯历史。
    try:
        import _assetcheck
        _ac_level = "FAIL" if (strict_assets and not (web / "final.mp4").exists()) else "WARN"
        ac_rows, _ = _assetcheck.check(ep, missing_chapter_level=_ac_level)
        ac_fail = [r for r in ac_rows if r[0] == "FAIL"]
        ac_warn = [r for r in ac_rows if r[0] == "WARN"]
        if ac_fail:
            add("FAIL", "素材盘点", "；".join(d for _, _, d in ac_fail))
        elif ac_warn:
            add("WARN", "素材盘点", "；".join(d for _, _, d in ac_warn))
        else:
            add("PASS", "素材盘点", "三表齐，表 B 清零，scenes.js 引用的音效/画材都在库")
    except Exception as e:
        add("WARN", "素材盘点", f"对账脚本报错（不阻塞渲染）：{e}")

    # 8 _ALL.wav + 配音新鲜度
    allwav = ep / "audio" / "_tmp" / "_ALL.wav"
    sp = ep / "script.py"
    if not allwav.exists():
        add("FAIL", "_ALL.wav", "缺（build_voice 没跑？A01 就是从这来的）")
    elif sp.exists() and sp.stat().st_mtime > allwav.stat().st_mtime:
        add("FAIL", "配音新鲜度",
            "script.py 比 _ALL.wav 新 → 台词改过但没重配（A01）；从 gen_cues/tts 重走")
    else:
        add("PASS", "_ALL.wav", f"{allwav.stat().st_size / 1024 / 1024:.1f} MB，不旧于 script.py")

    # 9 已交付（pub_ok 在段完整性那一段已算出）
    add("PASS" if pub_ok else "WARN", "已交付", f"40 出版物/{date}/{no}" if pub_ok else "还没交付")

    # ---- 汇总 ----
    print()
    for level, item, detail in results:
        mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[level]
        print(f"  {mark} {level:<4} {item:<14} {detail}")
    n_fail = sum(1 for r in results if r[0] == "FAIL")
    n_warn = sum(1 for r in results if r[0] == "WARN")
    print()
    print(f"合计 {len(results)} 项：PASS {len(results) - n_fail - n_warn} / WARN {n_warn} / FAIL {n_fail}")
    if n_fail:
        print("→ 有 %d 条 FAIL，先修再渲。" % n_fail)
        return 1
    if n_warn:
        # 硬要求（工具清单）：有 WARN 不许打「全绿」，项名逐条列出来，不许只写个数
        _names = "、".join(dict.fromkeys(item for lv, item, _ in results if lv == "WARN"))
        print("→ 可以开渲，但有 %d 条 WARN 需确认：%s" % (n_warn, _names))
        return 0
    print("→ 全绿，可以开渲。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
