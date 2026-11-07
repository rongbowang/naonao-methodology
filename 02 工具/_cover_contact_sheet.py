# -*- coding: utf-8 -*-
"""把七期的封面候选排成一个总览页，按「版式」分组，每个版式三比例并排，点图看原图。"""
import os, glob

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = [
    ("NO.17", "NO.17_等一句话", "一百个人等一句话"),
    ("NO.18", "NO.18_围一圈报数", "围一圈报数"),
    ("NO.19", "NO.19_地球加长一米", "地球加长一米"),
    ("NO.20", "NO.20_住满的旅馆", "住满的旅馆"),
    ("NO.21", "NO.21_两扇门", "两扇门"),
    ("NO.22", "NO.22_少了一格", "少了一格"),
    ("NO.23", "NO.23_蒙眼分硬币", "蒙眼分硬币"),
]
VARS = [("A", "经典 · 图上字下"), ("B", "侧置 · 图旁字"), ("E", "对撞 · 两句上下"),
        ("F", "巨数 · 数字加注解"), ("G", "大字报 · 纯文字黄底"),
        ("P", "上图下文 · 金带压字"), ("Q", "出血大图 · 白字压图"),
        ("R", "左右分栏 · 黄蓝对切"), ("S", "证物卡 · 歪卡片红章"),
        ("T", "数字出血 · 红底巨数")]
MODES = [("", "竖 1080×1440"), ("_横版", "横 1440×1080"), ("_16x9", "16:9 1920×1080")]

rows = []
for no, ep, slug in EPS:
    d = os.path.join(WORK, "30 制作", ep, "30_交付", "_候选")
    if not os.path.isdir(d):
        continue
    n = len(glob.glob(os.path.join(d, "*.png")))
    import json
    cf = os.path.join(WORK, '30 制作', ep, 'covers.json')
    slug = json.load(open(cf, encoding='utf-8')).get('slug') or slug
    blocks = []
    for v, vlabel in VARS:
        cells = []
        for suf, slabel in MODES:
            fn = "封面%s_%s_%s%s.png" % (v, no, slug, suf)
            p = os.path.join(d, fn)
            if os.path.exists(p):
                rel = "30 制作/%s/30_交付/_候选/%s" % (ep, fn)
                cells.append('<figure><a href="%s" target="_blank"><img loading="lazy" src="%s"></a>'
                             '<figcaption>%s</figcaption></figure>' % (rel, rel, slabel))
        if cells:
            blocks.append('<div class="grp"><h3>%s %s</h3><div class="row">%s</div></div>'
                          % (v, vlabel, "".join(cells)))
    rows.append('<section><h2>%s · %s <span>%d 张</span></h2>%s</section>'
                % (no, ep.split("_", 1)[1], n, "".join(blocks)))

HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>封面候选总览 2026-11-02</title>
<style>
 body{margin:0;padding:28px 32px 80px;background:#0A1522;color:#EAF2FF;
      font-family:"Microsoft YaHei","PingFang SC",sans-serif}
 h1{font-size:26px;margin:0 0 6px;letter-spacing:.04em}
 .hint{color:#8AA0BE;font-size:14px;margin-bottom:26px;line-height:1.7}
 section{margin:0 0 46px;border-top:1px solid #1B2C42;padding-top:22px}
 h2{font-size:20px;color:#FFD166;margin:0 0 14px}
 h2 span{color:#8AA0BE;font-size:13px;font-weight:400;margin-left:8px}
 .grp{margin:0 0 20px}
 h3{font-size:14px;color:#8AA0BE;font-weight:600;margin:0 0 8px;letter-spacing:.06em}
 .row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
 figure{margin:0;background:#0E1D30;border-radius:8px;padding:8px;width:196px}
 figure img{width:100%;display:block;border-radius:4px;background:#060F1A}
 figcaption{font-size:11px;color:#7C90AA;text-align:center;margin-top:6px}
</style></head><body>
<h1>封面候选总览 · 2026-11-02</h1>
<div class="hint">七期 × 10 版式 × 3 比例。点任意一张看原尺寸。挑的时候告诉我「NO.xx 用哪个字母」，我就按那版定稿并同步到交付目录与出版归档。</div>
""" + "".join(rows) + "</body></html>"

out = os.path.join(WORK, "封面候选_总览.html")
open(out, "w", encoding="utf-8").write(HTML)
print("写好了：%s（%d KB）" % (out, os.path.getsize(out) // 1024))
