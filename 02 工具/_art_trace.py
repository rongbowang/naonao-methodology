# -*- coding: utf-8 -*-
"""_art_trace.py — 把一张图（照片/版画/剪影）描成 100×100 单色线稿

为什么要有它：手写 path 全靠想象，形状一定走形（树懒画了两版都不像）。
这里走的是「先找参照 → 自动描边 → 再手工挑」的正路。

用法：
  python _art_trace.py 参考/简笔画/ref_zodiac_wheel.jpg --crop 120,140,440,520 \
      --thr 150 --inv --min-area 30 --out /tmp/zodiac.svg

参数：
  --crop  x0,y0,x1,y1   先裁（像素）
  --thr   0-255         二值阈值；版画/白底线稿给 ~150，深底图给 ~90
  --inv                 反相（深底亮线时用）
  --min-area            丢掉小于这个像素面积的斑点（去噪）
  --turdsize            potrace 的斑点抑制，一般 2~20
"""
import argparse, sys
import numpy as np
from PIL import Image
import potrace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("--crop", default="")
    ap.add_argument("--thr", type=int, default=150)
    ap.add_argument("--inv", action="store_true")
    ap.add_argument("--min-area", type=int, default=30)
    ap.add_argument("--turdsize", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=0)   # 先把图缩到这个宽，细节越少越干净
    ap.add_argument("--blur", type=float, default=0) # 二值前高斯模糊，把网点糊掉
    ap.add_argument("--tol", type=float, default=0.4)
    a = ap.parse_args()

    im = Image.open(a.img).convert("L")
    if a.crop:
        x0, y0, x1, y1 = [int(v) for v in a.crop.split(",")]
        im = im.crop((x0, y0, x1, y1))
    if a.size and im.size[0] > a.size:
        im = im.resize((a.size, int(im.size[1] * a.size / im.size[0])), Image.LANCZOS)
    if a.blur:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.GaussianBlur(a.blur))
    w, h = im.size
    arr = np.asarray(im).astype(np.uint8)
    mask = arr < a.thr
    if a.inv:
        mask = ~mask

    # 简单去噪：连通域小于 min-area 的丢掉（没有 cv2 也能做，用 potrace 的 turdsize 代替）
    bmp = potrace.Bitmap(mask)
    path = bmp.trace(turdsize=a.turdsize, alphamax=1.0, opticurve=True, opttolerance=a.tol)

    k = 100.0 / max(w, h)
    ox = (100 - w * k) / 2.0
    oy = (100 - h * k) / 2.0
    def P(p):
        return "%.2f %.2f" % (ox + p.x * k, oy + p.y * k)

    parts = []
    n_curve = 0
    for curve in path:
        d = ["M " + P(curve.start_point)]
        for seg in curve:
            n_curve += 1
            if seg.is_corner:
                d.append("L " + P(seg.c) + " L " + P(seg.end_point))
            else:
                d.append("C " + P(seg.c1) + " " + P(seg.c2) + " " + P(seg.end_point))
        d.append("Z")
        parts.append(" ".join(d))

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n'
           '<g fill="none" stroke="currentColor" stroke-width="3" '
           'stroke-linecap="round" stroke-linejoin="round">\n'
           '<path d="%s"/>\n</g></svg>\n') % " ".join(parts)
    open(a.out, "w", encoding="utf-8").write(svg)
    print("曲线段 %d，输出 %s" % (n_curve, a.out))


if __name__ == "__main__":
    main()
