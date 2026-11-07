# -*- coding: utf-8 -*-
"""重画两个题材图形：
   crowd —— 原来下半截画了「圆 + 粗横线 + 两条短竖线」，实际渲染出来像一把钥匙，
            「三个人 + 一把钥匙」完全读不出「一百个人」。改成前后两排五个人。
   gate  —— 原来门下的守卫只有一个圆 + 四条竖线，像蜘蛛。改成两个「头 + 肩」的小人。
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

P = os.path.join(HERE, "_webtmpl", "js", "cover_arts.js")

NEW_CROWD = '''  crowd: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="31" cy="34" r="10"/><path d="M14 82 C 14 54, 48 54, 48 82"/>
      <circle cx="70" cy="30" r="10"/><path d="M53 82 C 53 50, 87 50, 87 82"/>
      <circle cx="15" cy="56" r="8"/><path d="M2 92 C 2 71, 28 71, 28 92"/>
      <circle cx="50" cy="52" r="9"/><path d="M35 92 C 35 68, 65 68, 65 92"/>
      <circle cx="85" cy="56" r="8"/><path d="M72 92 C 72 71, 98 71, 98 92"/>
    </g>`},'''

NEW_GATE = '''  gate: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <rect x="10" y="10" width="30" height="60" rx="2"/>
      <rect x="60" y="10" width="30" height="60" rx="2"/>
      <circle cx="34" cy="40" r="2" fill="currentColor"/>
      <circle cx="66" cy="40" r="2" fill="currentColor"/>
      <circle cx="25" cy="80" r="5"/>
      <path d="M16 96 C 16 87, 34 87, 34 96"/>
      <circle cx="75" cy="80" r="5"/>
      <path d="M66 96 C 66 87, 84 87, 84 96"/>
    </g>`},'''


def rep(s, key, new):
    i = s.find("  %s: { body: `" % key)
    if i < 0:
        print("  ! 找不到 %s" % key); return s
    j = s.find("`},", i)
    j += 3
    print("  %s：%d -> %d 字符" % (key, j - i, len(new)))
    return s[:i] + new + s[j:]


def fn(s):
    s = rep(s, "crowd", NEW_CROWD)
    s = rep(s, "gate", NEW_GATE)
    return s


rewrite_file(P, fn)
print("  ok %d" % os.path.getsize(P))
