# -*- coding: utf-8 -*-
"""电影感基础层（吸收 STYLE.md；按已确认决策：3:4 / 中文主+英文微注 / 保留 Manim）

提供的可复用组件：
  - bg_layer(scene)        深蓝底 + 程序化噪点 + 径向暗角（一次性烘焙到 bg_full.png）
  - chapter(scene,...)      左上章节角标：编号 + 中文 + 英文微注 + 年份
  - style_scene(scene,...)  一次性：bg_layer + chapter（在每个场景 construct 开头调用）
  - en_label(scene,...)     英文微标注（每图 1~2 处全大写小字）
  - big_num(scene,...)      大字锚点（年份/数字/结论单独占屏）
调色板沿用 common（去紫）：BG/INK/GOLD/CORAL/GREEN/BLUE/CYAN/MUTED。
"""
import os
import numpy as np
from PIL import Image
from manim import ImageMobject
from common import *  # noqa: F401,F403

_HERE = os.path.dirname(os.path.abspath(__file__))
BG_EDGE = "#060D18"   # 暗角边缘（比 BG 更深）


def _ensure_bg():
    """烘焙一张 1080x1440 的底色图：BG 实色 + 径向暗角 + 极淡噪点。"""
    p = os.path.join(_HERE, "bg_full.png")
    if os.path.exists(p):
        return p
    W, H = 1080, 1440
    base = np.array(Image.new("RGB", (W, H), BG)).astype(np.float32)
    cx, cy = W / 2.0, H / 2.0
    maxr = float(np.sqrt(cx * cx + cy * cy))
    ys, xs = np.mgrid[0:H, 0:W]
    r = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / maxr
    vig = np.clip((r - 0.42) / 0.58, 0.0, 1.0)
    vig = (vig ** 1.5) * 140.0          # 边缘最多 ~140/255 压暗
    edge = np.array(Image.new("RGB", (W, H), BG_EDGE)).astype(np.float32)
    out = base * (1.0 - vig[:, :, None] / 255.0) + edge * (vig[:, :, None] / 255.0)
    out = out.astype(np.uint8)
    noise = np.random.RandomState(11).randint(0, 22, (H, W)).astype(np.float32)
    nimg = np.stack([noise, noise, noise], axis=-1)
    out = (out.astype(np.float32) * (1.0 - 0.05) + nimg * 0.05).clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(p)
    return p


def bg_layer(scene):
    """铺满整帧的电影感底色（噪点+暗角），置于最底层。"""
    p = _ensure_bg()
    img = ImageMobject(p)
    img.scale_to_fit_width(9.0)          # 帧宽 9（3:4 -> 9x12），等比高度=12
    img.move_to(vec(0, 0))
    img.set_z_index(-100)
    scene.add(img)
    return img




def style_scene(scene):
    """每个场景 construct 开头调用：铺电影感底色（噪点+暗角）。

    2026-10-18 用户反馈：左上角章节角标把制作内部术语直接怼给观众
    （第一镜出现「00 钩子 HOOK 1996」），且字体重叠 —— 章节角标已整体移除。
    电影感只保留底色 / 暗角 / 噪点；num/cn/en/year 参数保留仅为不改调用点。
    """
    bg_layer(scene)


def en_label(scene, txt, pos, size=13, color=MUTED):
    """英文微标注（全大写小字，每图 1~2 处）。"""
    t = T(txt, size=size, color=color).move_to(pos)
    t.set_z_index(45)
    scene.add(t)
    return t


def big_num(scene, txt, pos, color=GOLD, size=92):
    """大字锚点（年份/数字/结论单独占屏）。"""
    t = T(txt, size=size, color=color, weight=BOLD).move_to(pos)
    t.set_z_index(45)
    return t
