# -*- coding: utf-8 -*-
"""封面细节修：R 标题断行 / T 顶部漏字 / Q 图形太暗 / coin 图形重画。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

HTML = os.path.join(HERE, "_webtmpl", "cover_unified.html")
ARTS = os.path.join(HERE, "_webtmpl", "js", "cover_arts.js")

FIX_HTML = [
    # R 版：4 字标题在 48% 宽里 148px 放不下，被切成 3+1，降到 112px 一行放下
    ("body.r .title{left:5%;transform:none;width:48%;text-align:left;top:27%;\n    font-size:148px;line-height:1.04;color:#0A1A2F;text-shadow:none}",
     "body.r .title{left:5%;transform:none;width:52%;text-align:left;top:26%;\n    font-size:112px;line-height:1.06;color:#0A1A2F;text-shadow:none}"),
    ("body.h.r .title{width:44%;font-size:104px;top:26%}",
     "body.h.r .title{width:44%;font-size:92px;top:26%}"),
    ("body.w.r .title{font-size:112px}",
     "body.w.r .title{font-size:100px}"),
    # Q 版：图形太暗（0.26），压在白字后面几乎看不见
    ("body.q .art{left:50%;transform:translate(-50%,-50%);top:42%;width:840px;\n    color:var(--gold);opacity:.26}",
     "body.q .art{left:50%;transform:translate(-50%,-50%);top:44%;width:920px;\n    color:var(--gold);opacity:.42}"),
    # T 版：.sub 没定位，跑到画面顶上被切一半
    ("body.t .sig{color:rgba(255,255,255,.6)}",
     "body.t .sub{display:none}\n  body.t .sig{color:rgba(255,255,255,.6)}"),
    # T 版标题再大一点
    ("body.t .title{left:0;width:100%;transform:none;text-align:center;top:67%;font-size:52px;color:#FFFFFF;letter-spacing:.08em;line-height:1.35;",
     "body.t .title{left:0;width:100%;transform:none;text-align:center;top:66%;font-size:66px;color:#FFFFFF;letter-spacing:.10em;line-height:1.30;"),
]

OLD_COIN_START = '  /* 硬币堆 + 一只手：三摞硬币，右手从下方伸进来 */'
OLD_COIN_END = '    <circle cx="50" cy="70" r="7" fill="currentColor" opacity=".9"/>`},'

NEW_COIN = '''  /* 硬币：两摞叠起来的硬币 + 两枚散落的 */
  coin: { body: `
    <g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="26" cy="58" rx="14" ry="5.2"/><path d="M12 58 L12 66 A14 5.2 0 0 0 40 66 L40 58"/>
      <ellipse cx="26" cy="66" rx="14" ry="5.2"/><path d="M12 66 L12 74"/>
      <ellipse cx="26" cy="74" rx="14" ry="5.2"/><path d="M12 74 L12 82 A14 5.2 0 0 0 40 82 L40 74"/>
      <ellipse cx="26" cy="82" rx="14" ry="5.2"/>
      <ellipse cx="62" cy="66" rx="16" ry="5.8"/><path d="M46 66 L46 74 A16 5.8 0 0 0 78 74 L78 66"/>
      <ellipse cx="62" cy="74" rx="16" ry="5.8"/><path d="M46 74 L46 82"/>
      <ellipse cx="62" cy="82" rx="16" ry="5.8"/>
      <ellipse cx="88" cy="90" rx="9" ry="3.6"/><ellipse cx="90" cy="80" rx="9" ry="3.6"/>
    </g>`},'''


def fix_html(s):
    n = 0
    for a, b in FIX_HTML:
        if a in s:
            s = s.replace(a, b); n += 1
        else:
            print("  ! 未匹配：%s" % a[:44])
    print("  HTML 改 %d/%d 处" % (n, len(FIX_HTML)))
    return s


def fix_coin(s):
    i = s.find(OLD_COIN_START)
    j = s.find(OLD_COIN_END)
    if i < 0 or j < 0:
        print("  ! coin 锚点没找到"); return s
    j += len(OLD_COIN_END)
    print("  重画 coin（%d 字符 -> %d）" % (j - i, len(NEW_COIN)))
    return s[:i] + NEW_COIN + s[j:]


rewrite_file(HTML, fix_html)
rewrite_file(ARTS, fix_coin)
print("  ok")
