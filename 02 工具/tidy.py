#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tidy.py — 目录体检与整理（默认只看不动）

## 用法

    python tidy.py                      # 只出报告，不动任何文件（默认）
    python tidy.py --purge-plan         # 额外输出"可删除清单"到 99 归档/_清理清单_<日期>.txt
    python tidy.py --apply-archive      # 把 B 类（旧备份）移进 99 归档/_旧备份/<日期>/
    python tidy.py --apply-purge        # 真删 A 类（过程产物）—— 必须再加 --yes 才执行

**默认永远不删、不移。** 所有破坏性动作都要显式开关 + `--yes` 二次确认。

## 分类口径

A 类 · 验证产物（可删，重跑即得）
    <期>/web/_pilot/          单镜试渲分段
    <期>/web/pilot_*.mp4      单镜试渲成品
    <期>/web/_frames/         抽帧 png
    <期>/web/*.png            人眼检查截图（chk_ / _all_ / _d2_ / _v5_ …）
                             例外：_douyin_* / _sheet* 疑似交付尺寸图与拼图，保留

基础中间产物 · **保留**（删了要重渲全片，成本高）
    <期>/web/_seg/            分段 mp4
    <期>/audio/_tmp/_ALL.wav  整条配音

B 类 · 旧备份（该归档，不该躺在工作目录）
    *.orig / *.bak / *.__old / *.__old.<数字>

C 类 · 保留（脚本不碰）
    render.mp4 / final.mp4    成片
    audio/shots/*.wav         逐镜配音（重配要花钱）
    audio/_tmp/_ALL.wav       整条配音，重配才用得上
    timeline.json / voice.wav / scenes.js / script.py

D 类 · 位置可疑（只报告，不移动）
    项目根目录下的 *.md / *.html（交付说明、总览页应进 99 归档 或 10 内容）

## 安全边界

- **绝不进入** `20 素材_只读`、`.git`、`.workbuddy`、`99 归档` 内部。
- 只删除 A 类里**单个文件**与它们所在的 `_seg`/`_frames` 目录，不递归删期目录。
- 期目录是否"已交付"会被检查：`40 出版物/<日期>/` 下没有对应期号时，
  A 类**默认不列入删除**（还没交付就删过程产物，等于自断退路）。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "30 制作"
PUB = ROOT / "40 出版物"
ARCH = ROOT / "99 归档"
FORBIDDEN = {"20 素材_只读", ".git", ".workbuddy", "99 归档"}

A_DIRS = {"_pilot", "_frames"}          # 验证产物：试渲、抽帧 → 可删
KEEP_DIRS = {"_seg"}                    # 基础中间产物：分段 mp4 → **保留**
PNG_EXEMPT = ("_douyin_", "_sheet")     # 疑似交付尺寸图/拼图 → 保留
B_RE = re.compile(r"\.(orig|bak|old)$|__old(\.\d+)?$", re.I)


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _walk(base: Path):
    """遍历但不进入禁入目录。"""
    for dirpath, dirnames, filenames in os.walk(base):
        d = Path(dirpath)
        rel = d.relative_to(ROOT)
        dirnames[:] = [x for x in dirnames if str(rel / x) not in FORBIDDEN
                       and (rel / x).parts[0] not in FORBIDDEN]
        for f in filenames:
            yield d / f


def discover_eps():
    """[(期目录名, 期号, 日期)]，期号来自 script.py 的 NO 字段。"""
    out = []
    if not PROD.is_dir():
        return out
    for d in sorted(PROD.iterdir()):
        if not d.is_dir():
            continue
        sp = d / "script.py"
        no = ""
        if sp.exists():
            try:
                m = re.search(r'^NO\s*=\s*["\'](NO\.\d+)["\']',
                              sp.read_text(encoding="utf-8"), re.M)
                if m:
                    no = m.group(1)
            except Exception:
                pass
        out.append((d.name, no, d.name[:10]))
    return out


def delivered(no: str, date: str) -> bool:
    """40 出版物/<date>/ 下是否有这个期号。没期号的（旧目录）按已交付算。"""
    if not no:
        return True
    day = PUB / date
    if not day.is_dir():
        return False
    for sub in day.iterdir():
        if no in sub.name:
            return True
    return False


def scan():
    a_items, b_items, d_items, keep_items = [], [], [], []
    eps = discover_eps()

    for ep_name, no, date in eps:
        ep = PROD / ep_name
        ok_deliver = delivered(no, date)
        for f in _walk(ep):
            rel = f.relative_to(ROOT)
            parts = rel.parts
            # A 类
            if len(parts) >= 3 and parts[2] == "web":
                sub = parts[3] if len(parts) > 4 else ""
                name = f.name
                is_a = (
                    sub in A_DIRS
                    or (sub == "" and f.suffix.lower() == ".png"
                        and not name.startswith(PNG_EXEMPT))
                    or (sub == "" and name.startswith("pilot_") and f.suffix.lower() == ".mp4")
                )
                if is_a:
                    a_items.append((ep_name, ok_deliver, f, _size(f)))
                    continue
                if sub in KEEP_DIRS:
                    keep_items.append((ep_name, f, _size(f)))
                    continue
            # B 类
            if B_RE.search(f.name):
                b_items.append((ep_name, f, _size(f)))

    # 根目录 D 类
    for f in ROOT.iterdir():
        if f.is_file() and f.suffix.lower() in (".md", ".html", ".txt"):
            if f.name in ("README.md", ".gitignore"):
                continue
            d_items.append((f, _size(f)))

    return a_items, b_items, d_items, keep_items


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge-plan", action="store_true", help="把可删除清单写到 99 归档")
    ap.add_argument("--apply-archive", action="store_true", help="移走 B 类旧备份")
    ap.add_argument("--apply-purge", action="store_true", help="删除 A 类过程产物")
    ap.add_argument("--yes", action="store_true", help="配合 --apply-purge 的二次确认")
    a = ap.parse_args()

    a_items, b_items, d_items, keep_items = scan()

    a_all = sum(s for _, _, _, s in a_items)
    a_unsafe = sum(s for _, ok, _, s in a_items if not ok)
    b_all = sum(s for _, _, s in b_items)
    d_all = sum(s for _, s in d_items)
    k_all = sum(s for _, _, s in keep_items)

    print("=" * 68)
    print("A 类 · 验证产物（可删）")
    print(f"  {len(a_items)} 个文件，{human(a_all)}")
    print(f"  其中所在期尚未交付的：{human(a_unsafe)}（默认不列入删除）")
    by_ep = {}
    for ep, ok, f, s in a_items:
        by_ep.setdefault(ep, [0, 0, ok])
        by_ep[ep][0] += 1
        by_ep[ep][1] += s
        by_ep[ep][2] = by_ep[ep][2] and ok
    for ep, (n, s, ok) in sorted(by_ep.items(), key=lambda x: -x[1][1])[:12]:
        flag = "" if ok else "  ← 未交付，跳过"
        print(f"    {ep:<34} {n:>4} 个  {human(s):>9}{flag}")

    print()
    print("保留（脚本不碰）")
    print(f"  基础中间产物 {len(keep_items)} 个，{human(k_all)}  ← _seg 分段，删了要重渲全片")
    print("  最终产物     render.mp4 / final.mp4 / audio/_tmp/_ALL.wav / 30_交付 / 40 出版物")

    print()
    print("B 类 · 旧备份（该归档）")
    print(f"  {len(b_items)} 个文件，{human(b_all)}")
    for _, f, _ in b_items[:8]:
        print(f"    {f.relative_to(ROOT)}")
    if len(b_items) > 8:
        print(f"    … 另 {len(b_items) - 8} 个")

    print()
    print("D 类 · 位置可疑（只报告）")
    for f, s in d_items:
        print(f"    {f.name}  {human(s)}")

    print()
    print("=" * 68)
    print(f"可释放合计（A 类安全部分 + B 类）：{human(a_all - a_unsafe + b_all)}")

    if a.purge_plan:
        ARCH.mkdir(exist_ok=True)
        out = ARCH / f"_清理清单_{time.strftime('%Y%m%d_%H%M')}.txt"
        with out.open("w", encoding="utf-8") as fh:
            for ep, ok, f, s in sorted(a_items, key=lambda x: str(x[2])):
                fh.write(f"{'KEEP' if not ok else 'DEL '}\t{human(s):>10}\t{f}\n")
        print(f"\n清单已写：{out}")

    if a.apply_archive:
        dst_root = ARCH / "_旧备份" / time.strftime("%Y%m%d")
        moved = 0
        for _, f, _ in b_items:
            dst = dst_root / f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.move(str(f), str(dst))
                moved += 1
        print(f"\n已归档 {moved} 个旧备份 → {dst_root}")

    if a.apply_purge:
        if not a.yes:
            print("\n✗ --apply-purge 需要同时加 --yes（先看报告，再删）")
            return 1
        removed = 0
        freed = 0
        for _, ok, f, s in a_items:
            if not ok:
                continue
            try:
                f.unlink()
                removed += 1
                freed += s
            except OSError as e:
                print(f"  ! 删除失败 {f}: {e}")
        print(f"\n已删除 {removed} 个文件，释放 {human(freed)}")
        print("空的 _seg/_frames 目录保留（下次渲染会复用）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
