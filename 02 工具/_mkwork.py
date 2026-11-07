# -*- coding: utf-8 -*-
"""_mkwork.py — 把一期工程复制成一个「本机可写」的工作副本

共享盘上另一台机器创建的旧文件对本机只读（新建文件可写）。
复制出来的是「本机新建的文件」，就全都能写了，管线不用改。

用法:
    python _mkwork.py v51_blueeyes v51b_blueeyes            # 整目录复制（排除大文件）
    python _mkwork.py v51_blueeyes v51b_blueeyes --script script_v4_150s.py
"""
import io
import os
import shutil
import sys

SKIP_EXT = {".png", ".jpg", ".jpeg", ".mp4", ".mp3", ".svg"}
ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    src = sys.argv[1]
    dst = sys.argv[2]
    script = None
    if "--script" in sys.argv:
        script = sys.argv[sys.argv.index("--script") + 1]

    s, d = os.path.join(ROOT, src), os.path.join(ROOT, dst)
    os.makedirs(d, exist_ok=True)
    n = 0
    for base, dirs, files in os.walk(s):
        dirs[:] = [x for x in dirs if x not in ("_tmp", "frames", "node_modules", "cues", "shots")]
        rel = os.path.relpath(base, s)
        tgt = d if rel == "." else os.path.join(d, rel)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SKIP_EXT and not (rel.replace("\\", "/").startswith("web") and ext == ".png" and f == ""):
                pass
            if ext in (".mp4", ".mp3"):
                continue
            if f.startswith("_b") and ext == ".png":
                continue
            sp = os.path.join(base, f)
            try:
                shutil.copy2(sp, os.path.join(tgt, f))
                n += 1
            except Exception as e:
                print("  skip %s (%s)" % (sp, e.__class__.__name__))

    # 素材（片尾脑子）
    ass = os.path.join(ROOT, "_webtmpl", "assets")
    if os.path.isdir(ass):
        shutil.copytree(ass, os.path.join(d, "web", "assets"), dirs_exist_ok=True)

    if script:
        txt = io.open(os.path.join(s, script), encoding="utf-8").read()
        if "NO = " not in txt:
            txt = txt.replace("BAODIAN = ", 'NO = "NO.%s"\nBAODIAN = ' % "".join(
                c for c in dst.split("_")[0] if c.isdigit()), 1)
        io.open(os.path.join(d, "script.py"), "w", encoding="utf-8", newline="").write(txt)
        print("  script.py <- %s" % script)

    print("OK  %s -> %s   (%d files)" % (src, dst, n))


if __name__ == "__main__":
    main()
