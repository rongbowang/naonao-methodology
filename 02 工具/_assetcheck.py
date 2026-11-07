#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_assetcheck.py — 素材三方对账（契约：references/工具清单.md「_assetcheck.py 契约」，2026-11-07 定）

    python _assetcheck.py NO.29
    python _assetcheck.py 2026-11-13_皮托悖论      # 也允许直接传期目录

对三方：06_画面绘制.md 的 `## 素材盘点` 三表 ↔ graphics_catalog.json / sfx_catalog.json
↔ scenes.js 实际引用的音效 id 与画材函数。任一查不到 = FAIL。

六条判据（契约原文）：
  1  06 有 `## 素材盘点` 章，且含 `### 表 A / 表 B / 表 C`
  2  表 B 每行「入库状态」含 `✅ 已入库`（空白/待补/⚠️ 都算没做完）
  3  表 C 标 ✅ 的音效 id 能在 sfx_catalog.json 的 sounds[].id 查到
  4  scenes.js 里 sfx( 调用的字符串实参（含 mux.py SFX_ALIAS 别名）都能在库查到
     —— mux 对查不到的 id 是静默跳过，这是音效消失的根因
  5  scenes.js 里 A.<name>( / P.<name>( 的 <name> 必须在本期 web/js/props*.js（含 assets.js）里定义
  6  表 B 图形类素材的名字能在 graphics_catalog.json 的 items[].name 里找到

解析方式：markdown 表格逐行按 `|` 切、跳过分隔行，不做全文正则猜表。
退出码：0 = PASS（WARN 不算 FAIL） / 1 = FAIL / 2 = 找不到期。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROD = ROOT / "30 制作"
SFX_CAT = ROOT / "20 素材_只读" / "sfx_catalog.json"
GFX_CAT = ROOT / "20 素材_只读" / "graphics_catalog.json"

ID_LIKE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")   # 音效 id 形态：kebab-case


# ---------- 复用 preflight 的期号解析（不另写一套） ----------

def find_ep(arg: str):
    sys.path.insert(0, str(HERE))
    import preflight
    return preflight.find_ep(arg)


# ---------- 数据加载 ----------

def _load_sfx_ids() -> set:
    try:
        d = json.loads(SFX_CAT.read_text(encoding="utf-8"))
        return {s.get("id", "") for s in d.get("sounds", []) if s.get("id")}
    except Exception:
        return set()


def _load_gfx_names() -> list:
    try:
        d = json.loads(GFX_CAT.read_text(encoding="utf-8"))
        return [str(x.get("name", "")) for x in d.get("items", []) if x.get("name")]
    except Exception:
        return []


def _load_alias(web: Path) -> dict:
    """mux.py 的 SFX_ALIAS：自编名 → 库真 id。别名键也算可解析（mux 会换名）。"""
    p = web / "mux.py"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"SFX_ALIAS\s*=\s*\{(.*?)\}", t, re.S)
    if not m:
        return {}
    return dict(re.findall(r"""["']([^"']+)["']\s*:\s*["']([^"']+)["']""", m.group(1)))


# ---------- scenes.js 抽取 ----------

def _sfx_ids_in_scenes(txt: str):
    """契约判据 4：sfx(...) 调用里的字符串实参（括号配平扫描，防 W(shot,...) 嵌套漏采）。
    另扫 name:"id" 赋值作补充（音效表常写成 {name:"..."}，再由 sfx(box,s.t,s.name,...) 派发）。"""
    from_call, from_name = {}, {}
    for m in re.finditer(r"\bsfx\s*\(", txt):
        i = m.end()          # 停在 '(' 后
        depth = 1
        while i < len(txt) and depth:
            c = txt[i]
            if c in "\"'":                       # 跳过字符串字面量
                q = c
                i += 1
                while i < len(txt) and txt[i] != q:
                    i += 2 if txt[i] == "\\" else 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        args = txt[m.end():i - 1]
        for lit in re.findall(r"""["']([^"'\n]+)["']""", args):
            v = lit.strip()
            if ID_LIKE.match(v):
                from_call[v] = from_call.get(v, 0) + 1
    for m in re.finditer(r"""\bname\s*[:=]\s*["']([^"'\n]+)["']""", txt):
        v = m.group(1).strip()
        if ID_LIKE.match(v):
            from_name[v] = from_name.get(v, 0) + 1
    return from_call, from_name


def _props_names(web: Path) -> set:
    """本期画材里定义过的名字：props*.js + assets.js 的函数/方法/导出键。"""
    names = set()
    files = sorted(web.glob("js/props*.js")) + [web / "js" / "assets.js"]
    for f in files:
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        names |= set(re.findall(r"\bfunction\s+([A-Za-z_]\w*)\s*\(", t))
        names |= set(re.findall(r"([A-Za-z_]\w*)\s*:\s*function", t))
        names |= set(re.findall(r"\bconst\s+([A-Za-z_]\w*)\s*=\s*(?:function|\()", t))
    return names


def _props_calls(txt: str):
    """契约判据 5：scenes.js 里 A.<name>( / P.<name>( 形态的调用。
    接收者若在本文件被 const/let/var 局部声明（如 const P = [[0,0],...] 的坐标数组），
    静态分析分不清指向，一律跳过不判 —— 宁可漏报不误报。"""
    shadowed = {m.group(1) for m in re.finditer(r"\b(?:const|let|var)\s+([AP])\s*[=,)]", txt)}
    calls = []
    for m in re.finditer(r"\b([AP])\s*\.\s*([A-Za-z_]\w*)\s*\(", txt):
        recv, name = m.group(1), m.group(2)
        if recv in shadowed:
            continue
        calls.append((recv, name))
    return calls


def _destructured_props(txt: str) -> set:
    """scenes.js 里 const { a, b } = window.PROPS/ASSET/PROPS_GRID 解构出来的名字也算已定义。"""
    out = set()
    for m in re.finditer(r"\{([^{}]*)\}\s*=\s*window\.(?:PROPS\w*|ASSET\w*)", txt):
        for part in m.group(1).split(","):
            nm = part.strip().split(":")[-1].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", nm):
                out.add(nm)
    return out


# ---------- markdown 三表解析（逐行切，跳过分隔行） ----------

def _chapter(md: str):
    m = re.search(r"^##\s*素材盘点\s*$", md, re.M)
    if not m:
        return None
    body = md[m.end():]
    nxt = re.search(r"^##\s+\S", body, re.M)          # 下一章（### 不算）
    return body[: nxt.start()] if nxt else body


def _parse_table(seg: str):
    rows = []
    for line in seg.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break                                  # 表格结束
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue                                   # |---|---| 分隔行
        rows.append(cells)
    return rows


def _tables(chap: str):
    out = {}
    for key in "ABC":
        m = re.search(r"^###\s*表\s*" + key + r"\b", chap, re.M)
        out[key] = _parse_table(chap[m.end():]) if m else None
    return out


def _gfx_found(name: str, gfx: list) -> str:
    """表 B 图形名 → catalog items[].name：精确(忽略大小写)或双向包含。返回命中的名或 ''。"""
    t = name.strip().lower()
    if not t:
        return ""
    for n in gfx:
        nl = n.lower()
        if t == nl or (len(t) >= 3 and (t in nl or nl in t)):
            return n
    return ""


# ---------- 主检查 ----------

def check(ep: Path, missing_chapter_level: str = "FAIL"):
    """返回 (rows, n_fail)。rows = [(level, item, detail), ...]
    missing_chapter_level：06 缺章的级别。preflight 调用时传 "WARN"（老文档只提醒），
    独立运行默认 "FAIL"（§5.4 是作画硬闸门）。"""
    rows = []

    def add(level, item, detail=""):
        rows.append((level, item, detail))

    web = ep / "web"
    doc = ep / "06_画面绘制.md"
    scenes = web / "js" / "scenes.js"
    sfx_ids = _load_sfx_ids()
    gfx_names = _load_gfx_names()
    alias = _load_alias(web)

    if not sfx_ids:
        add("FAIL", "素材盘点·库", f"sfx_catalog.json 读不出（{SFX_CAT.name}）")
    if not gfx_names:
        add("FAIL", "素材盘点·库", f"graphics_catalog.json 读不出（{GFX_CAT.name}）")

    # ---- 判据 1：章与三表 ----
    chap = None
    if not doc.exists():
        add(missing_chapter_level, "素材盘点·三表", "06_画面绘制.md 还没写，未做素材盘点，作画前必须补")
    else:
        chap = _chapter(doc.read_text(encoding="utf-8", errors="ignore"))
        if chap is None:
            add(missing_chapter_level, "素材盘点·三表", "06 里没有 ## 素材盘点 章，未做素材盘点，作画前必须补")
        else:
            tb = _tables(chap)
            missing = [k for k in "ABC" if tb[k] is None]
            if missing:
                add("FAIL", "素材盘点·三表", "章在，但缺 " + "、".join(f"表 {k}" for k in missing))
            else:
                add("PASS", "素材盘点·三表", "## 素材盘点 + 表 A/B/C 齐")

    # ---- 判据 2 / 3 / 6（要在章里才查得动） ----
    tb = _tables(chap) if chap else {"A": None, "B": None, "C": None}

    if tb["B"] is not None:
        bad, ok_n = [], 0
        for cells in tb["B"]:
            if cells and cells[0] == "素材":          # 表头行
                continue
            name = cells[0] if cells else ""
            status = cells[4] if len(cells) > 4 else ""
            if "✅" in status and "已入库" in status:
                ok_n += 1
            else:
                bad.append(f"「{name}」状态=“{status or '空'}”")
        if bad:
            add("FAIL", "素材盘点·表B", f"{len(bad)} 行没清零（必须先入库再作画）：{'；'.join(bad[:4])}"
                + ("…" if len(bad) > 4 else ""))
        else:
            add("PASS", "素材盘点·表B", f"{ok_n} 行全部 ✅ 已入库")

        # 判据 6：图形类必须登记进 graphics_catalog
        unreg = []
        for cells in tb["B"]:
            if not cells or cells[0] == "素材":
                continue
            rowtext = " ".join(cells)
            name = cells[0]
            is_graph = bool(re.search(r"graphics|图形库|图库|SVG", rowtext, re.I)) or \
                bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 _'&.-]{2,}", name))
            if is_graph and not _gfx_found(name, gfx_names):
                unreg.append(name)
        if unreg:
            add("FAIL", "素材盘点·登记", f"图形类未登记进 graphics_catalog：{'、'.join(unreg[:5])}"
                + ("…" if len(unreg) > 5 else "") + "（不登记 = 下一个人搜不到，等于没有）")

    if tb["C"] is not None:
        bad, pend = [], []
        for cells in tb["C"]:
            if cells and cells[0].lower() == "id":
                continue
            sid = cells[0].strip("`") if cells else ""
            status = cells[2] if len(cells) > 2 else ""
            if "✅" in status:
                if sid not in sfx_ids:
                    bad.append(sid or "（空 id）")
            elif "⚠" in status:
                pend.append(sid or "（未命名音效）")
        if bad:
            add("FAIL", "素材盘点·表C", f"标了 ✅ 但库里查不到：{'、'.join(bad[:5])}")
        elif pend:
            add("WARN", "素材盘点·表C", f"还有 {len(pend)} 条待入库音效：{'、'.join(pend[:5])}")
        else:
            add("PASS", "素材盘点·表C", "标 ✅ 的音效 id 全部在库")

    # ---- 判据 4：scenes.js 音效 id 三方对账 ----
    placeholder = scenes.exists() and scenes.stat().st_size < 3000   # 占位 stub（实测 158B~1558B，真实期 37K~68K）
    if scenes.exists():
        txt = scenes.read_text(encoding="utf-8", errors="ignore")
        from_call, from_name = _sfx_ids_in_scenes(txt)
        if placeholder and not from_call:
            add("WARN", "素材盘点·音效", "scenes.js 还是占位（<3KB），音效无可对账 —— 别当成已在库")
        else:
            miss_call = sorted(k for k in from_call if k not in sfx_ids and k not in alias)
            miss_name = sorted(k for k in from_name if k not in sfx_ids and k not in alias)
            bad_alias = sorted(v for v in alias.values() if v not in sfx_ids)
            if miss_call:
                add("FAIL", "素材盘点·音效",
                    f"scenes.js 的 sfx() 用了库里没有的 id（mux 会静默跳过）：{'、'.join(miss_call[:6])}"
                    + ("…" if len(miss_call) > 6 else ""))
            elif bad_alias:
                add("FAIL", "素材盘点·音效", f"mux.py SFX_ALIAS 指向的 id 也不在库：{'、'.join(bad_alias[:5])}")
            elif miss_name:
                add("WARN", "素材盘点·音效", f"name= 形式引用了库外 id（确认不是自造）：{'、'.join(miss_name[:6])}")
            else:
                add("PASS", "素材盘点·音效", f"sfx() 引用 {len(from_call)} 个 id 全部在库"
                    + (f"（另有 {len(alias)} 条 SFX_ALIAS 别名）" if alias else ""))
    else:
        add("WARN", "素材盘点·音效", "web/js/scenes.js 还没写，音效/画材对账跳过")

    # ---- 判据 5：A./P. 画材函数 ----
    if scenes.exists():
        txt = scenes.read_text(encoding="utf-8", errors="ignore")
        known = _props_names(web) | _destructured_props(txt)
        calls = _props_calls(txt)
        if placeholder and not calls:
            add("WARN", "素材盘点·画材", "画材同音效：scenes.js 还是占位（<3KB），无可对账")
        else:
            miss = sorted({n for _, n in calls if n not in known})
            if miss:
                add("FAIL", "素材盘点·画材",
                    f"A./P. 调用在本期 props*.js / assets.js 里找不到定义：{'、'.join(miss[:6])}")
            elif calls:
                add("PASS", "素材盘点·画材", f"{len(calls)} 处 A./P. 调用都有定义")
            else:
                add("PASS", "素材盘点·画材", "无 A./P. 直调（走 window.PROPS 解构），无需对账")

    n_fail = sum(1 for r in rows if r[0] == "FAIL")
    return rows, n_fail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ep, no = find_ep(sys.argv[1])
    if ep is None:
        print(f"!! 找不到这一期：{sys.argv[1]}")
        avail = [d.name for d in PROD.iterdir() if d.is_dir()] if PROD.is_dir() else []
        print("   现有：%s" % "、".join(avail))
        return 2

    rows, n_fail = check(ep)
    print("=" * 70)
    print(f"素材对账：{no or '（无期号）'}  {ep.name}")
    print("=" * 70)
    print()
    for level, item, detail in rows:
        mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[level]
        print(f"  {mark} {level:<4} {item:<14} {detail}")
    n_warn = sum(1 for r in rows if r[0] == "WARN")
    print()
    print(f"合计 {len(rows)} 项：PASS {len(rows) - n_fail - n_warn} / WARN {n_warn} / FAIL {n_fail}")
    if n_fail:
        print("→ 素材对账有 FAIL，先按 §5.4 入库/登记再作画。")
        return 1
    print("→ 素材对账通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
