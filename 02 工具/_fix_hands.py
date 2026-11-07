# -*- coding: utf-8 -*-
"""修 NO.22 / NO.23 的「人形无手」+ NO.23 蒙眼布歪斜。改完立刻 ast 无关，只有 JS。"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

WORK = os.path.dirname(HERE)


def show_hands(s):
    """删掉所有 body.P.handX.setAttribute("opacity", 0) 行"""
    n = len(re.findall(r'body\.P\.hand[LR]\.setAttribute\("opacity", 0\);', s))
    s = re.sub(r'\n[ \t]*body\.P\.hand[LR]\.setAttribute\("opacity", 0\);[ \t]*', '', s)
    return s, n


def fix_band(s):
    """蒙眼布：加宽到 1.30、去掉 -4 度旋转"""
    n1 = s.count('body.Rh * 2 * 1.12')
    s = s.replace('body.Rh * 2 * 1.12', 'body.Rh * 2 * 1.30')
    n2 = len(re.findall(r',\s*transform: "rotate\(-4\)"', s))
    s = re.sub(r',\s*transform: "rotate\(-4\)"', '', s)
    # 注释同步
    s = s.replace('布带：宽 = 头径 × 1.12', '布带：宽 = 头径 × 1.30，水平居中不旋转')
    return s, (n1, n2)


def go(proj, band=False):
    p = os.path.join(WORK, "30 制作", proj, "web", "js", "scenes.js")
    src = open(p, encoding="utf-8").read()
    before = len(src)

    def fn(s):
        out = {}
        s, n = show_hands(s)
        out["hands"] = n
        if band:
            s, (a, b) = fix_band(s)
            out["bw"] = a
            out["rot"] = b
        print("  %s -> 删手 %d 处%s" % (proj, out["hands"],
              (", 布宽 %d 处, 去旋转 %d 处" % (out["bw"], out["rot"])) if band else ""))
        return s

    rewrite_file(p, fn)
    after = len(open(p, encoding="utf-8").read())
    print("  %d -> %d 字节" % (before, after))


if __name__ == "__main__":
    go("NO.23_蒙眼分硬币", band=True)
    go("NO.22_少了一格", band=False)
