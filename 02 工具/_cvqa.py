"""_cvqa.py — 封面客观质检（我看不了图，只能靠数字判断版面有没有塌）

三个指标：
  1. 对比度：全图亮度标准差 + P5/P95 分位差。低饱和/低对比 = 信息流里隐身
  2. 分块占用：把图切 3 列 × 2 行，每块算「内容密度」（局部标准差）。
     某块接近 0 = 那一块是空的 → 横版容易出现「元素全挤左边、右边一片死白」
  3. 10% 缩略可读：缩到手机信息流大小再算一次对比度，掉太多说明字太细

用法：python _cvqa.py <目录>
"""
import sys, os, glob
from PIL import Image, ImageStat, ImageFilter

def metrics(im):
    g = im.convert("L")
    st = ImageStat.Stat(g)
    mean, sd = st.mean[0], st.stddev[0]
    h = g.histogram()
    n = sum(h)
    def pct(p):
        acc = 0
        for i, c in enumerate(h):
            acc += c
            if acc >= n * p:
                return i
        return 255
    p5, p95 = pct(.05), pct(.95)
    return mean, sd, p95 - p5

def blocks(im, cols=3, rows=2):
    """每块的边缘密度（Sobel 近似：与模糊版的差）"""
    g = im.convert("L")
    w, h = g.size
    edge = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0]
    out = []
    for r in range(rows):
        for c in range(cols):
            box = (c * w // cols, r * h // rows, (c + 1) * w // cols, (r + 1) * h // rows)
            sub = g.crop(box)
            out.append(ImageStat.Stat(sub.filter(ImageFilter.FIND_EDGES)).mean[0] / max(0.5, edge))
    return out

def main(d):
    files = sorted(glob.glob(os.path.join(d, "*.png")))
    if not files:
        print("没有 png"); return
    print("%-40s %6s %6s %6s %s" % ("文件", "均值", "SD", "P5-95", "分块占用(左→右,上→下)"))
    print("-" * 104)
    warn = []
    for f in files:
        im = Image.open(f)
        mean, sd, rng = metrics(im)
        b = blocks(im)
        lo = min(b)
        # 缩略后对比保留率：缩到信息流大小还剩多少层次
        th = im.copy(); th.thumbnail((160, 160))
        _, sds, _ = metrics(th)
        keep = sds / max(1e-6, sd)
        tag = ""
        # ★ SD 不作主判据：暗底单元素封面（v4）天然低，不代表看不清。
        #   改用「明暗跨度」——P5~P95 有没有拉开，以及缩略后层次掉没掉。
        if rng < 110:
            tag += " ⚠明暗跨度不足"
        if lo < 0.30:
            tag += " ⚠有近空块"
        if keep < 0.65:
            tag += " ⚠缩略后糊"
        if tag:
            warn.append(os.path.basename(f))
        print("%-40s %6.1f %6.1f %6d %s%s" % (
            os.path.basename(f)[:40], mean, sd, rng,
            " ".join("%.2f" % x for x in b), tag))
        print("%-40s %6s %6s %6s 缩略 SD=%.1f（保留 %.0f%%）" % ("", "", "", "", sds, keep * 100))
    print()
    print("判据：P5-95<110 明暗跨度不足 / 任一块占用<0.30 该区域空白 / 缩略保留<65% 细节糊")
    print("（SD 只作参考：暗底单主体封面 SD 天然偏低，不代表不合格）")
    print(("待看：" + ", ".join(warn)) if warn else "✅ 全部通过")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
