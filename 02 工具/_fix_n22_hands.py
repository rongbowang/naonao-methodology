# -*- coding: utf-8 -*-
"""NO.22：把手抬到躯干中部（默认挂在衣角，像两个球黏在衣服下摆）。"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

WORK = os.path.dirname(HERE)
P = os.path.join(WORK, "30 制作", "NO.22_少了一格", "web", "js", "scenes.js")

SNIP = '''  body.g.setAttribute("opacity", 1);
  /* 手抬到躯干中部（islander 默认把手挂在躯干下缘，像两个球黏在衣角） */
  (function (b) {
    const hy = +(b.armY + b.H * 0.40 * 0.28).toFixed(1);
    ["handL", "handR"].forEach((k) => { if (b.P[k]) b.P[k].setAttribute("cy", hy); });
    ["armL", "armR"].forEach((k) => { if (b.P[k]) b.P[k].setAttribute("y2", hy); });
  })(body);'''

OLD = '  body.g.setAttribute("opacity", 1);'


def fn(s):
    n = s.count(OLD)
    s = s.replace(OLD, SNIP)
    print("  插入 %d 处" % n)
    return s


rewrite_file(P, fn)
print("  完成 %d 字节" % os.path.getsize(P))
