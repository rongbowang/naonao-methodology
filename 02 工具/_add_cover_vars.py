# -*- coding: utf-8 -*-
"""给统一封面加两个图形主导版式：P（图形轰击）与 S（分屏对撞）。

为什么不用字母 H/K：body 的 class 里 h/v/w 已经是「横版/竖版/16:9」的 mode 标记，
版式字母必须避开 h。P = pop（图形轰击），S = split（分屏对撞）。
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

P = os.path.join(HERE, "_webtmpl", "cover_unified.html")

CSS = r'''
  /* ============================================================
     2026-11-02 新增两版「图形主导」（用户：不能全是字，要有张力）
       P 图形轰击：图形出血占屏 60%+，标题压在图上，撞色底
       S 分屏对撞：一半亮黄一半深蓝，两句话各占一半，图形跨在深色侧
     只动布局，颜色仍然只用 :root 那 7 个
     ============================================================ */

  /* ---------- P 图形轰击 ---------- */
  body.p #cover{background:#081426}
  body.p .base{background:
    radial-gradient(80% 55% at 50% 34%, rgba(255,209,102,.22), transparent 62%),
    linear-gradient(180deg,#0C1E36 0%,#0A1A2F 52%,#060F1D 100%)}
  body.p .art{color:var(--gold);opacity:.92;
    filter:drop-shadow(0 0 70px rgba(255,209,102,.45))}
  body.p .badge{top:4.2%;font-size:30px;padding:13px 32px;letter-spacing:.3em}
  body.p .title{top:52%;font-size:172px;letter-spacing:.02em;
    text-shadow:0 0 90px rgba(255,209,102,.55),0 10px 34px rgba(0,0,0,.85)}
  body.p .sub{top:73.5%;font-size:34px;letter-spacing:.26em;padding:.2em .42em;
    background:rgba(10,26,47,.82);border-radius:999px}
  body.p .chips{top:80.5%;gap:18px}
  body.p .chip{font-size:40px;padding:9px 26px}
  body.p .sig{font-size:29px;color:var(--gold)}
  body.v.p .art{left:50%;transform:translateX(-50%);top:-7%;width:1340px}
  body.h.p .art{left:50%;transform:translateX(-50%);top:-24%;width:1560px}
  body.h.p .title{top:47%;font-size:186px}
  body.h.p .sub{top:70%}
  body.h.p .chips{top:79%}
  body.w.p .art{left:50%;transform:translateX(-50%);top:-30%;width:1720px}
  body.w.p .title{top:46%;font-size:196px}
  body.w.p .sub{top:70%}
  body.w.p .chips{top:79%}

  /* ---------- S 分屏对撞 ---------- */
  body.s #cover::before{content:"";position:absolute;z-index:1;
    background:linear-gradient(160deg,#FFD166 0%,#F0B93C 100%)}
  body.s .base,body.s .glow,body.s .noise,body.s .vig{opacity:.35}
  body.s .badge{z-index:3;top:3.6%;font-size:28px;padding:12px 30px;
    color:#0A1A2F;border-color:rgba(10,26,47,.4);background:rgba(255,255,255,.35)}
  body.s .etop,body.s .ebot{z-index:3;font-weight:900;letter-spacing:.02em;
    line-height:1.06;white-space:pre-line;text-align:center;left:50%;transform:translateX(-50%)}
  body.s .art{z-index:2;color:var(--gold);opacity:.95;
    filter:drop-shadow(0 0 50px rgba(255,209,102,.5))}
  body.s .sub{z-index:3;font-size:30px;letter-spacing:.24em}
  body.s .chips{z-index:3;gap:16px}
  body.s .chip{font-size:34px;padding:8px 22px}
  body.s .sig{z-index:3;font-size:27px;color:var(--gold)}
  /* 竖版：上黄下深 */
  body.v.s #cover::before{left:0;right:0;top:0;height:44%}
  body.v.s .etop{top:9%;font-size:132px;color:#0A1A2F}
  body.v.s .art{left:50%;transform:translateX(-50%);top:30%;width:820px}
  body.v.s .ebot{top:63%;font-size:118px;color:var(--gold)}
  body.v.s .sub{top:80%}
  body.v.s .chips{top:85.5%}
  /* 横版 / 16:9：左黄右深 */
  body.h.s #cover::before,body.w.s #cover::before{
    left:0;top:0;bottom:0;width:46%;height:auto;
    background:linear-gradient(120deg,#FFD166 0%,#F0B93C 100%)}
  body.h.s .etop,body.w.s .etop{left:23%;top:34%;font-size:126px;color:#0A1A2F}
  body.h.s .art,body.w.s .art{left:74%;top:40%;transform:translate(-50%,-50%);width:620px}
  body.h.s .ebot,body.w.s .ebot{left:23%;top:60%;font-size:112px;color:var(--gold)}
  body.w.s .etop{font-size:142px}
  body.w.s .ebot{font-size:126px}
  body.w.s .art{width:720px;top:42%}
  body.h.s .sub,body.w.s .sub{left:74%;transform:translateX(-50%);top:74%}
  body.h.s .chips,body.w.s .chips{left:74%;top:81%}
  body.h.s .sig,body.w.s .sig{color:var(--gold)}
'''


def fn(s):
    if "---------- P 图形轰击 ----------" in s:
        print("  版式已存在，跳过")
        return s
    i = s.rindex("</style>")
    print("  在 </style> 前插入 %d 字符" % len(CSS))
    return s[:i] + CSS + "\n" + s[i:]


rewrite_file(P, fn)
print("  完成 %d 字节" % os.path.getsize(P))
