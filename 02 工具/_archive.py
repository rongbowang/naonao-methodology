# -*- coding: utf-8 -*-
"""_archive.py — 把一期的成片 + 三版封面归档到 每日成果/<日期>/，旧版先备份。

用法：python _archive.py 2026-10-25 NO.11 8个正常人住进精神病院 v11_rosenhan

做的事：
  1. 每日成果/<日期>/_旧版备份/ 里存一份旧文件（只在首次出现时存，不覆盖已有备份）
  2. 拷 final.mp4 → <期号>_<标题>_竖屏.mp4
  3. 拷三版封面（竖版 / 横版 4:3 / 16x9）
  4. 删掉同目录下「同一期号但旧标题」的老文件，避免一期两份
"""
import glob
import json
import os
import re
import shutil
import sys

from _paths import PUB, proj_dir   # 归档容器 / 期工程目录（新旧兼容）


def main(date, no, title, proj):
    d = os.path.join(PUB, date)
    web = os.path.join(proj_dir(proj), "web")
    if not os.path.isdir(web):
        print("!! 没有这个工程：", web)
        return 1
    os.makedirs(d, exist_ok=True)
    bak = os.path.join(d, "_旧版备份")
    os.makedirs(bak, exist_ok=True)

    # 1) 旧版备份（不覆盖已存在的备份）
    for f in glob.glob(os.path.join(d, "*.mp4")) + glob.glob(os.path.join(d, "*.png")) + glob.glob(os.path.join(d, "*.txt")):
        t = os.path.join(bak, os.path.basename(f))
        if not os.path.exists(t):
            shutil.copy(f, t)

    # 2) 成片
    src = os.path.join(web, "final.mp4")
    # 画幅决定文件名（2026-11-03 起 16:9 是主线）
    try:
        _sz = json.load(open(os.path.join(web, "size.json"), encoding="utf-8"))
        _ori = "横屏" if int(_sz["width"]) > int(_sz["height"]) else "竖屏"
    except Exception:
        _ori = "竖屏"
    dst = os.path.join(d, "%s_%s_%s.mp4" % (no, title, _ori))
    shutil.copy(src, dst)
    print("  +", os.path.basename(dst), "%.1f MB" % (os.path.getsize(dst) / 1048576))

    # 3) 三版封面 —— 文件名取 covers.json 的 title（封面大字），不是目录名
    cover_title = title
    try:
        cj = os.path.join(proj, "covers.json")
        if os.path.exists(cj):
            cover_title = json.load(open(cj, encoding="utf-8")).get("title") or title
    except Exception:
        pass
    got = []
    for pat in ["封面_%s_%s.png" % (no, cover_title),
                "封面_%s_%s_横版.png" % (no, cover_title),
                "封面_%s_%s_16x9.png" % (no, cover_title)]:
        p = os.path.join(web, "out", pat)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(d, pat))
            got.append(pat)
            print("  +", pat)
        else:
            print("  !! 缺封面：", pat)

    # 4) 删掉同一期号的旧标题文件（备份里已经有了）
    for f in glob.glob(os.path.join(d, "%s_*" % no)):
        b = os.path.basename(f)
        if b not in got and b != os.path.basename(dst) and not b.startswith("标题与描述"):
            try:
                os.remove(f)
                print("  - 移除旧名", b)
            except Exception:
                # 共享盘 safe-delete 会拦 os.remove（0x80070002），
                # 删不掉不算失败 —— 文件已经在 _旧版备份 里了，别让归档中断。
                print("  ~ 旧文件删不掉（忽略）", b)
    for f in glob.glob(os.path.join(d, "封面_%s_*" % no)):
        b = os.path.basename(f)
        if b in got:
            continue
        # 2026-10-23 修的坑：只删「同一期号但不同标题」的旧封面。
        # 老工程 web/out 里常常只有竖版+横版，没有 16:9 —— 原来的逻辑会把
        # 上一轮补的 16:9 当成「旧文件名」删掉（NO.05~NO.09 就中招了）。
        if ("封面_%s_%s" % (no, title)) in b:
            continue
        try:
            os.remove(f)
            print("  - 移除旧封面", b)
        except Exception:
            print("  ~ 旧封面删不掉（忽略）", b)

    print("DONE", date, no)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
