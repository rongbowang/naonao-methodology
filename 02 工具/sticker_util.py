# -*- coding: utf-8 -*-
"""贴图库工具（2026-10-17）
把 `stickers/` 下的透明 PNG 用进 Manim，并支持「断肢从断点分开」的动画。

核心约定
--------
`<name>_body.png` 和 `<name>_tail.png` / `<name>_claw.png` 是**同一张画布**的两半
（另一半全透明）。所以两个 ImageMobject `move_to` 到同一个位置，就精确叠回完整图；
要表现"断掉"，只需把「断下来的部分」那一层移走 + 淡出，身体那层原地不动。

可用贴图（stickers/）
--------------------
  scorpion.png / scorpion_body.png / scorpion_tail.png
  gecko.png    / gecko_body.png    / gecko_tail.png
  crab.png     / crab_body.png     / crab_claw.png
  gecko_stub.png（尾断后再生出来的短桩）、crab_broken.png（缺一只钳的整蟹）

维护
----
原图是 ImageGen 生成的白底/模切白边图，`build_stickers.py` 负责抠底 + 切对。
改断点位置就改 `build_stickers.py` 里的 split_pair 比例，然后重跑。
"""
import os

from manim import ImageMobject

_HERE = os.path.dirname(os.path.abspath(__file__))
STK_DIR = os.path.join(_HERE, "stickers")


def sticker(name, height=2.0):
    """加载一张贴图并按高度缩放"""
    im = ImageMobject(os.path.join(STK_DIR, name).replace("\\", "/"))
    im.scale_to_fit_height(height)
    return im


def limb_pair(body_name, part_name, height=2.0, pos=None):
    """返回 (身体, 断下来的部分)；两者 move_to 同一点即叠回完整图"""
    from manim import ORIGIN
    p = ORIGIN if pos is None else pos
    body = sticker(body_name, height).move_to(p)
    part = sticker(part_name, height).move_to(p)
    return body, part


def scorpion_pair(height=2.0, pos=None):
    return limb_pair("scorpion_body.png", "scorpion_tail.png", height, pos)


def gecko_pair(height=1.6, pos=None):
    return limb_pair("gecko_body.png", "gecko_tail.png", height, pos)


def crab_pair(height=1.6, pos=None):
    return limb_pair("crab_body.png", "crab_claw.png", height, pos)
