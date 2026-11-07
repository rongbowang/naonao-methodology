#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_doccheck.py — 画面文档 ↔ script.py ↔ timeline.json 三方对账

    python _doccheck.py NO.29
    python _doccheck.py 2026-11-13_皮托悖论

## 为什么需要它

`06_画面绘制.md` 是给下一个 agent（或下一个会话的自己）看的施工图。
文档写「5 镜 / 48 句」而 timeline 是 7 镜，下一个 agent 就按错的施工；
文档里某个镜号改了名，动作锚全失效 —— 而且**没有任何报错**。

查这几项：

| 查什么 | 骗人的方式 |
|---|---|
| 镜号集合 | 文档多一镜/少一镜，或 id 拼错（`04_outro` 写成 `04_outro_`） |
| 每镜句数 | 逐句动作表写到第 7 句，台词只有 5 句 |
| 总句数 | 标题写「48 句」，实际 51 句 |
| 时长 / 画幅 | 文档抄了上一期的 `duration`，或还写着竖屏 |
| 安全区 | 文档写 ≤1104（竖屏旧值），`kit.js` 横屏是 760 |

退出码：对齐 → 0；有差异 → 1。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "30 制作"


def find_ep(arg: str):
    for d in sorted(PROD.iterdir()):
        if not d.is_dir():
            continue
        sp = d / "script.py"
        if arg == d.name:
            return d
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
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ep = find_ep(sys.argv[1])
    if ep is None:
        print(f"!! 找不到这一期：{sys.argv[1]}")
        return 2

    doc = ep / "06_画面绘制.md"
    tlp = ep / "web" / "timeline.json"
    if not doc.exists() or not tlp.exists():
        print(f"!! 缺文件：{'06_画面绘制.md' if not doc.exists() else 'web/timeline.json'}")
        return 2

    txt = doc.read_text(encoding="utf-8")
    tl = json.loads(tlp.read_text(encoding="utf-8"))
    tl_shots = {s.get("id"): len(s.get("lines", [])) for s in tl.get("shots", [])}

    print("=" * 66)
    print(f"对账：{ep.name}")
    print("=" * 66)

    problems = []

    # 1 标题声明的镜数/句数
    m = re.search(r'(\d+)\s*镜\s*/\s*(\d+)\s*句', txt)
    if m:
        d_shots, d_lines = int(m.group(1)), int(m.group(2))
        if d_shots != len(tl_shots):
            problems.append(f"标题写 {d_shots} 镜，timeline 实际 {len(tl_shots)} 镜")
        total = sum(tl_shots.values())
        if d_lines != total:
            problems.append(f"标题写 {d_lines} 句，timeline 实际 {total} 句")
        if not problems:
            print(f"  ✓ 标题声明 {d_shots} 镜 / {d_lines} 句，与 timeline 一致")
    else:
        problems.append("标题里没写「N 镜 / N 句」")

    # 2 镜号集合
    heads = [(mm.start(), mm.group(1))
             for mm in re.finditer(r'^##\s*\d+\.\s*([0-9]{2}_[a-z]+)', txt, re.M)]
    doc_ids = [h[1] for h in heads]
    if not heads:
        problems.append("文档里没解析出任何「## N. 镜号」标题")
    else:
        miss = [i for i in tl_shots if i not in doc_ids]
        extra = [i for i in doc_ids if i not in tl_shots]
        if miss:
            problems.append(f"文档缺镜：{'、'.join(miss)}")
        if extra:
            problems.append(f"文档多镜（timeline 里没有）：{'、'.join(extra)}")
        dup = [i for i in set(doc_ids) if doc_ids.count(i) > 1]
        if dup:
            problems.append(f"文档里镜号重复：{'、'.join(dup)}")
        if not (miss or extra or dup):
            print(f"  ✓ 镜号 {'、'.join(doc_ids)} 与 timeline 一一对应")

    # 3 每镜句数：只数「逐句动作表」里的连续 `| N |` 行
    #    （镜内还有「19 项清单」等首列也是数字的表，按整段取 max 会误判成 19）
    for i, (pos, sid) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(txt)
        body = txt[pos:end]
        mt = re.search(r'^###\s*逐句动作表', body, re.M)
        if not mt:
            continue
        nums = []
        seen_head = False
        for ln in body[mt.start():].split("\n"):
            if re.match(r'^\|\s*句\s*\|', ln):
                seen_head = True
                continue
            if not seen_head:
                continue
            mm = re.match(r'^\|\s*(\d{1,3})\s*\|', ln)
            if mm:
                nums.append(int(mm.group(1)))
            elif nums and not ln.strip().startswith("|"):
                break
        if not nums:
            continue
        d_n = len(nums)
        d_max = max(nums)
        t_n = tl_shots.get(sid)
        if t_n is not None and d_n != t_n:
            problems.append(f"{sid}：动作表 {d_n} 行（末句 {d_max}），台词 {t_n} 句")

    # 4 时长 / 画幅
    dur = re.search(r'duration\s*([\d.]+)\s*s', txt)
    if dur:
        d_dur = float(dur.group(1))
        if abs(d_dur - tl["duration"]) > 0.5:
            problems.append(f"文档 duration {d_dur}s，timeline {tl['duration']:.2f}s")
        else:
            print(f"  ✓ duration {d_dur}s 与 timeline 一致")
    size = re.search(r'(\d{3,4})\s*[×x]\s*(\d{3,4})', txt)
    if size:
        w, h = int(size.group(1)), int(size.group(2))
        if (w, h) != (tl.get("width"), tl.get("height")):
            problems.append(f"文档画幅 {w}×{h}，timeline {tl.get('width')}×{tl.get('height')}")

    # 5 安全区：必须有 ≤760（元素底边）；只有 ≤990/≤1104 是竖屏旧口径
    if re.search(r'≤\s*760', txt):
        print("  ✓ 声明了元素底边 ≤760")
    elif re.search(r'≤\s*(990|1104)', txt):
        problems.append("文档只写了 ≤990/≤1104，没有元素底边 ≤760（横屏 SAFE_BOT）")
    else:
        problems.append("文档没写元素底边 ≤760")

    print()
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        print(f"\n{len(problems)} 处不一致 —— 文档已经和实现对不上了")
        return 1
    print("✓ 文档、script.py、timeline 三方对齐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
