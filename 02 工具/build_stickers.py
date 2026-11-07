# -*- coding: utf-8 -*-
"""贴图库构建脚本（2026-10-17）
输入：stickers/ 下 ImageGen 生成的原图（白底 / 模切白边 / 带投影 / 带右下角水印）
输出：透明 PNG + 断肢变体（左右两半同画布 / 断尾层 / 无尾版 / 断钳版）

抠底算法（key_soft）：
  ImageGen 的 background=transparent 实际没生效，出来的是白底；壁虎那张还是
  「模切白边 + 柔和投影」。纯白容差抠不掉那圈灰边，所以改成按
  「亮度高 + 饱和度低」判背景（min(R,G,B)>150 且 max-min<45），
  再从边框洪水填充，只剥掉**连通到画布外**的那部分——动物体内的浅色不会被误伤。
用法：python build_stickers.py
"""
import os
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
STK = os.path.join(HERE, "stickers")

# 原图文件名 → 逻辑名
SRC = {
    "scorpion":      "A_realistic_scorpion__full_bod_2026-10-17T12-18-01.png",
    "gecko":         "A_realistic_leopard_gecko_liza_2026-10-17T12-18-37.png",
    "gecko_stub":    "A_realistic_leopard_gecko_liza_2026-10-17T12-21-24.png",
    "crab":          "A_realistic_crab__top_down_vie_2026-10-17T12-20-45.png",
    "crab_broken":   "A_realistic_crab__top_down_vie_2026-10-17T12-21-06.png",
}


def key_soft(path, wipe=(185, 82), feather=1.1):
    """抠底（2026-10-17 v4，前几版都错在同一个坑里）

    坑：PIL 的 ImageDraw.floodfill **在 'L' 模式图上不填充**（只 RGB 模式有效），
    导致 keep 全 True、抠底完全没发生——图看着"还行"其实是因为贴在白底卡片上。
    现在改用 scipy 的连通域标记：给 bgish 打标签，凡**摸到画布边框**的标签才是真背景。

    步骤：涂掉右下角水印 → 判背景（亮且低饱和）→ 只剥连通到画布外的背景
          → 收 1px 再羽化（去白边）→ 补"被轮廓包住的背景口袋"→ 近白着暖色
    """
    im = Image.open(path).convert("RGB")
    W, H = im.size
    ImageDraw.Draw(im).rectangle([W - wipe[0] - 6, H - wipe[1] - 6, W - 2, H - 2],
                                 fill=(255, 255, 255))
    rgb = np.asarray(im).astype(np.int16)
    mn = rgb.min(axis=2)
    spread = rgb.max(axis=2) - mn
    bgish = (mn > 150) & (spread < 45)            # 白 / 灰 / 模切边 / 投影

    # 8-连通标记背景域，只有摸到画布边框的才算"画布外的背景"
    lab, n = ndimage.label(bgish, structure=np.ones((3, 3), dtype=int))
    if n:
        edge = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) \
               | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
        edge.discard(0)
        keep = ~np.isin(lab, list(edge))
    else:
        keep = ~bgish

    # 收 1 像素再羽化：否则最外那圈"白→本体"过渡像素被留着，会形成一圈亮边
    keep = ndimage.binary_erosion(keep, iterations=1)

    # 补口袋：被动物轮廓包住的背景（螃蟹腿缝 / 壁虎肚子下的投影）不连通到画布外，
    # 会被保留 → 对**整块都是浅色**的小组件单独清零。
    # 判据用"组件内没有任何高饱和像素"，所以壁虎断尾的浅色尾桩（带深色尖端）不误删。
    colored = (spread >= 45) | (mn <= 150)
    lab2, n2 = ndimage.label(keep)
    for i in range(n2):
        sl = ndimage.find_objects(lab2)[i]
        if sl is None:
            continue
        sel = lab2[sl] == i + 1
        if sel.sum() >= 4000:
            continue
        if not colored[sl][sel].any():
            keep[sl][sel] = False

    alpha = Image.fromarray((keep * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(feather))
    rgba = np.dstack([rgb.astype(np.int16), np.asarray(alpha).astype(np.int16)])

    # 近白着暖色：残留浅色区（壁虎尾桩、腿缝白）染成皮色，免得在深色画面上像白补丁
    w = (mn > 195) & (spread < 50) & (rgba[..., 3] > 200)
    warm = np.array([226, 196, 150], dtype=np.int16)
    rgba[..., :3][w] = (rgba[..., :3][w] * 0.42 + warm * 0.58).astype(np.uint8)
    return Image.fromarray(rgba.astype(np.uint8), "RGBA")


def trim(im, pad=8):
    bb = im.split()[3].getbbox()
    if bb:
        l, t, r, b = bb
        im = im.crop((max(0, l - pad), max(0, t - pad),
                      min(im.width, r + pad), min(im.height, b + pad)))
    return im


def norm_h(im, h=760):
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)


def save(im, name):
    im.save(os.path.join(STK, name))
    print("  -> %-20s %s" % (name, im.size))


print("== 抠底 ==")
src = {k: norm_h(trim(key_soft(os.path.join(STK, f)))) for k, f in SRC.items()}
for k, v in src.items():
    save(v, "%s.png" % k)


def split_pair(im, cut, part_side="right"):
    """把一张图沿 cut 切成「身体」和「断下来的部分」。
    **两张都是同一张画布**（其余区域全透明），所以在 Manim 里 move_to 到同一位置
    就能精确叠回原图；断的时候只把「断下来的部分」那一层移走 + 淡出。

    part_side="right"：断掉的部分在切线右边（蝎子尾、壁虎尾）
    part_side="left" ：断掉的部分在切线左边（螃蟹的左钳在画面左侧）
    """
    W, H = im.size
    x = int(W * cut)
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left = blank.copy(); left.alpha_composite(im.crop((0, 0, x, H)), (0, 0))
    right = blank.copy(); right.alpha_composite(im.crop((x, 0, W, H)), (x, 0))
    if part_side == "right":
        return left, right
    return right, left


def mask_pair(im, poly, blur=1.0):
    """用多边形 mask 分离「身体」和「断下来的部分」。
    poly: [(x0,y0), ...] 为归一化坐标 (0..1)，包围断下来的部分。
    返回 (body, part) 同画布透明 PNG，叠放后等于原图。
    """
    W, H = im.size
    mask = Image.new("L", (W, H), 0)
    pts = [(int(p[0] * W), int(p[1] * H)) for p in poly]
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body = Image.composite(im, blank, ImageChops.invert(mask))
    part = Image.composite(im, blank, mask)
    return body, part


print("== 断肢对（同画布，叠放 = 完整图）==")
# 蝎子：只圈出真正的尾节（metasoma + telson），躯干 broad body 保留在 body 层。
# 坐标基于处理后的 scorpion.png（1008x760）。
SCORPION_TAIL_POLY = [
    (0.76, 0.32), (0.78, 0.20), (0.83, 0.10), (0.91, 0.05),
    (0.98, 0.12), (0.98, 0.26), (0.93, 0.40), (0.83, 0.52),
    (0.74, 0.58), (0.65, 0.48), (0.70, 0.34),
]
b, t = mask_pair(src["scorpion"], SCORPION_TAIL_POLY)
save(b, "scorpion_body.png"); save(t, "scorpion_tail.png")
b, t = split_pair(src["gecko"], 0.72)         # 尾根（条纹尾起处）
save(b, "gecko_body.png"); save(t, "gecko_tail.png")
b, t = split_pair(src["crab"], 0.17, part_side="left")   # 左钳在画面左侧，断件在切线左边
save(b, "crab_body.png"); save(t, "crab_claw.png")

print("== 自检：body+part 叠回去必须等于原图 ==")
for base, bn, pn in [("scorpion", "scorpion_body.png", "scorpion_tail.png"),
                     ("gecko", "gecko_body.png", "gecko_tail.png"),
                     ("crab", "crab_body.png", "crab_claw.png")]:
    a = np.asarray(src[base])
    L = Image.open(os.path.join(STK, bn)); R = Image.open(os.path.join(STK, pn))
    comp = Image.new("RGBA", L.size, (0, 0, 0, 0))
    comp.alpha_composite(L); comp.alpha_composite(R)
    diff = np.abs(np.asarray(comp).astype(int) - a.astype(int))
    print("  %-9s 最大通道差=%d  平均差=%.3f" % (base, diff.max(), diff.mean()))

print("== 完成 ==")
