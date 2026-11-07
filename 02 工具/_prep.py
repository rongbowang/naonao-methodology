# -*- coding: utf-8 -*-
r"""_prep.py — 让管线能重新生成文件（共享盘只允许「新建」，不允许「改写旧文件」）

## 现象（2026-10-31 复现）
`\\192.168.1.3\Naonao` 上：
    open(已有文件, 'w')      -> PermissionError
    open(不存在路径, 'w')    -> OK
    os.rename(已有文件, 新名) -> OK

所以凡是「重新生成」都会失败，但把它换成新文件就会成功。
这个脚本把待重新生成的产物先改名让位（<名字>.old_<时间戳>），
管线再写时就变成「新建」，一路畅通。

## 用法
    python _prep.py v53_paper          # 清一期的产物
    python _prep.py v53_paper --dry    # 只看会动哪些文件
"""
import os
import sys
import time

# 每期跑管线会重新生成的东西（相对工程目录）
TARGETS = [
    "cues.json",
    "audio/_tmp",
    "audio/shot_meta.json",
    "audio/cues_meta.json",
    "audio/cues_text.json",
    "web/timeline.json",
    "web/timeline.js",
    "web/voice.wav",
    "web/render.mp4",
    "web/final.mp4",
    "web/_concat",
    "web/_mix.wav",
    "web/_voice_norm.wav",
    "web/sfx.json",
    "web/_seg",
    "web/_frames",
    "web/out",
    "audio/shots",
]
# 目录里逐个文件挪的
DIRS = ["audio/cues"]


def uniq(p):
    base = p + ".old_%s" % time.strftime("%H%M%S")
    q, i = base, 1
    while os.path.exists(q):
        i += 1
        q = base + "_%d" % i
    return q


def move(p, dry):
    if not os.path.exists(p):
        return 0
    if dry:
        print("  would move", p)
        return 1
    os.rename(p, uniq(p))
    print("  moved", p)
    return 1


def main():
    proj = sys.argv[1]
    if not os.path.isdir(proj):       # 传的是期名，走统一路径解析
        from _paths import proj_dir
        proj = proj_dir(proj)
    dry = "--dry" in sys.argv
    print("[prep]", proj, "(dry)" if dry else "")
    n = 0
    for t in TARGETS:
        n += move(os.path.join(proj, t), dry)
    for d in DIRS:
        dd = os.path.join(proj, d)
        if os.path.isdir(dd):
            for f in sorted(os.listdir(dd)):
                n += move(os.path.join(dd, f), dry)
    print("  %d 项让位" % n)


if __name__ == "__main__":
    main()
