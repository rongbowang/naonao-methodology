# -*- coding: utf-8 -*-
"""给封面图形库补 4 个题材图形（描边 currentColor / viewBox 0 0 100 100 / 线宽 3）。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

P = os.path.join(HERE, "_webtmpl", "js", "cover_arts.js")

NEW = r'''
  /* ---- 2026-11-02 补：NO.17~NO.23 六期题材专用 ---- */

  /* 一圈人（约瑟夫环）：12 个圆点围成椭圆 + 一个被标红的空位 */
  ring: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="50" cy="52" rx="38" ry="26" stroke-dasharray="4 6" opacity=".5"/>
      <circle cx="50" cy="21" r="6"/><circle cx="63" cy="23" r="6"/><circle cx="74" cy="30" r="6"/>
      <circle cx="81" cy="41" r="6"/><circle cx="83" cy="54" r="6"/><circle cx="78" cy="67" r="6"/>
      <circle cx="66" cy="76" r="6"/><circle cx="50" cy="79" r="6"/><circle cx="34" cy="76" r="6"/>
      <circle cx="19" cy="41" r="6"/><circle cx="26" cy="30" r="6"/><circle cx="37" cy="23" r="6"/>
    </g>
    <g stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity=".9">
      <path d="M12 56 L24 68 M24 56 L12 68"/>
    </g>`},

  /* 硬币堆 + 一只手：三摞硬币，右手从下方伸进来 */
  coin: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="27" cy="62" rx="12" ry="4.5"/><path d="M15 62 L15 70 A12 4.5 0 0 0 39 70 L39 62"/>
      <ellipse cx="27" cy="70" rx="12" ry="4.5"/>
      <ellipse cx="27" cy="77" rx="12" ry="4.5"/>
      <ellipse cx="55" cy="47" rx="12" ry="4.5"/><path d="M43 47 L43 55 A12 4.5 0 0 0 67 55 L67 47"/>
      <ellipse cx="55" cy="55" rx="12" ry="4.5"/>
      <path d="M42 88 L58 88 M50 88 L50 74"/>
    </g>
    <circle cx="50" cy="70" r="7" fill="currentColor" opacity=".9"/>`},

  /* 方格少一格：4×4 网格，右下缺一块，旁边浮着一块 */
  grid: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <path d="M14 14 L74 14 L74 74 L14 74 Z"/>
      <path d="M34 14 L34 74 M54 14 L54 74 M14 34 L74 34 M14 54 L74 54"/>
      <path d="M54 54 L54 74 M54 74 L74 74" stroke-width="0" />
    </g>
    <rect x="55" y="55" width="19" height="19" fill="none" stroke="currentColor"
      stroke-width="3" stroke-dasharray="4 5" opacity=".55"/>
    <rect x="80" y="26" width="15" height="15" fill="currentColor" opacity=".85"/>`},

  /* 一只被蒙住的眼睛：横向布带压住眼，露出眉和睫毛 */
  eyepatch: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <path d="M10 44 C 26 26, 74 26, 90 44"/>
      <path d="M10 60 C 26 78, 74 78, 90 60"/>
      <rect x="8" y="44" width="84" height="16" rx="8" fill="currentColor" opacity=".16"/>
      <path d="M8 46 L92 46 M8 58 L92 58"/>
      <path d="M22 27 L18 20 M50 22 L50 14 M78 27 L82 20"/>
    </g>`},

  /* 两扇门 + 一真一假两个守卫：门对立，脚下各站一个小人 */
  gate: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <rect x="10" y="12" width="30" height="58" rx="2"/>
      <rect x="60" y="12" width="30" height="58" rx="2"/>
      <circle cx="34" cy="42" r="2" fill="currentColor"/>
      <circle cx="66" cy="42" r="2" fill="currentColor"/>
      <path d="M18 78 L18 88 M32 78 L32 88 M68 78 L68 88 M82 78 L82 88"/>
    </g>
    <circle cx="50" cy="80" r="6" fill="currentColor"/>`},
'''


def fn(s):
    anchor = "window.ARTS = {"
    i = s.index(anchor) + len(anchor)
    # 如果已经加过就跳过
    if "ring: { body:" in s and "gate: { body:" in s:
        print("  图形已存在，跳过")
        return s
    print("  插入 5 个图形")
    return s[:i] + NEW + s[i:]


rewrite_file(P, fn)
print("  完成 %d 字节" % os.path.getsize(P))
