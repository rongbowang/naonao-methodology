# -*- coding: utf-8 -*-
"""通用动画工具库（从 v5_parrondo/scenes.py 提取，供各期 scenes.py 共用）"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from common import *  # noqa: F401,F403
from style_lib import *  # noqa: F401,F403
import numpy as np


# 本地覆写：默认 linear（匀速 = 逐帧像素变化恒定；smooth 的缓动尾巴会被判成静止帧）
_orig_seq_play = seq_play


def seq_play(scene, steps, dur, min_rt=0.05):
    steps = [(s[0], s[1], s[2] if len(s) > 2 else linear) for s in steps]
    _orig_seq_play(scene, steps, dur, min_rt)


def seq_abs(scene, steps, dur, min_rt=0.05):
    """与 seq_play 相同，但 steps 的权重按**绝对秒**解释；最后一步吸收剩余时长。
    （seq_play 的权重是相对比例，设 0.2s 会实际播出 dur*0.2/总权重 —— 慢 FadeIn 会被判静止）"""
    left = float(dur)
    n = len(steps)
    for i, step in enumerate(steps):
        anims, w = step[0], step[1]
        rf = step[2] if len(step) > 2 else None
        rt = left if i == n - 1 else min(float(w), left)
        rt = max(rt, min_rt)
        args = list(anims) if isinstance(anims, (list, tuple)) else [anims]
        scene.play(*args, run_time=rt, rate_func=(rf if rf is not None else linear))
        left -= rt




# =====================================================================
# 通用零件
# =====================================================================
def slot_machine(color=BLUE, scale=1.0):
    """老虎机：机身 + 三个转轮（内含会滚动的标记）+ 拉杆 + 出币口。
    返回 (整体, 转轮标记组) —— 给标记组加 updater 就是「一直在转」。"""
    g = VGroup()
    body = RoundedRectangle(width=2.0, height=2.55, corner_radius=0.20,
                            fill_color=color, fill_opacity=0.16,
                            stroke_color=color, stroke_width=4)
    g.add(body)
    marks = VGroup()
    for i in range(3):
        fr = Rectangle(width=0.46, height=0.92, fill_color=BG, fill_opacity=0.92,
                       stroke_color=color, stroke_width=2.4).move_to(
            vec(-0.63 + i * 0.63, 0.42))
        g.add(fr)
        for k in (-0.22, 0.22):
            mk = RoundedRectangle(width=0.30, height=0.16, corner_radius=0.05,
                                  fill_color=GOLD, fill_opacity=0.90,
                                  stroke_width=0).move_to(
                vec(-0.63 + i * 0.63, 0.42 + k))
            g.add(mk)
            marks.add(mk)
    arm = Line(vec(1.12, 0.60), vec(1.12, -0.30), color=MUTED, stroke_width=6)
    knob = Dot(vec(1.12, -0.34), color=GOLD, radius=0.13)
    slot = Rectangle(width=1.25, height=0.26, fill_color=BG, fill_opacity=0.92,
                     stroke_color=MUTED, stroke_width=2).move_to(vec(0, -0.95))
    g.add(arm, knob, slot)
    g.scale(scale)
    return g, marks


def reel_updater(marks, amp=0.20, period=0.55):
    """转轮一直滚动。**更新器必须挂在每个标记上**（挂在未入场的 VGroup 上永远不会被触发）"""
    base = [m.get_center()[1] for m in marks]
    for i, mk in enumerate(marks):
        st = {"t": i * 0.09}

        def _upd(mm, dt, st=st, i=i, base=base):
            st["t"] += dt
            off = amp * np.sin(TAU * st["t"] / period + i * 0.9)
            mm.move_to(vec(mm.get_center()[0], base[i] + off))
        mk.add_updater(_upd)
    return marks


def drop_loop(mob, top, bottom, period=1.15):
    """循环下落并渐隐（机器一直在吐币）——用来填「旁白还在说、主体已动完」的空档"""
    st = {"t": 0.0}

    def _upd(m, dt):
        st["t"] = (st["t"] + dt) % period
        k = st["t"] / period
        m.move_to(top + (bottom - top) * k)
        m.set_opacity(max(0.0, 1.0 - k * 1.15))
    mob.add_updater(_upd)
    return mob


def flip_loop(mob, base_mob, center, period=1.05):
    """硬币不停翻面（余弦展宽）——持续提供画面运动"""
    st = {"t": 0.0}

    def _upd(m, dt):
        st["t"] += dt
        k = abs(np.cos(TAU * st["t"] / period))
        m.become(base_mob.copy().stretch(max(k, 0.05), dim=0).move_to(center))
    mob.add_updater(_upd)
    return mob


def hold_motion(scene, dur):
    """撑满剩余节拍 —— 画面运动由**已挂的循环更新器**提供（wait 期间更新器照常跑）。
    （最后一步必须吃满节拍，否则成片会 tpad 定格）"""
    if dur > 0.05:
        scene.wait(dur)




def coin_mob(label="", color=GOLD, r=0.86):
    c = Circle(radius=r, fill_color=color, fill_opacity=0.20,
               stroke_color=color, stroke_width=5)
    g = VGroup(c)
    if label:
        g.add(T(label, size=28, color=color, weight=BOLD))
    return g


def coin_stack(n=4, color=GOLD, w=0.62, unit=0.13):
    """一摞金币（n 层）"""
    g = VGroup()
    for i in range(n):
        e = Ellipse(width=w, height=unit * 2, fill_color=color,
                    fill_opacity=0.85, stroke_color=color, stroke_width=2)
        e.move_to(vec(0, i * unit * 1.35))
        g.add(e)
    return g


def arrow_down(color=CORAL, size=0.55):
    return Arrow(vec(0, size), vec(0, -size), color=color, stroke_width=6,
                 buff=0, max_tip_length_to_length_ratio=0.45)


def arrow_up(color=GREEN, size=0.55):
    return Arrow(vec(0, -size), vec(0, size), color=color, stroke_width=6,
                 buff=0, max_tip_length_to_length_ratio=0.45)


def chip_num(txt, color=GOLD, size=34):
    """画面里只允许出现的『数字/百分比』或 ≤3 字标签"""
    return T(txt, size=size, color=color, weight=BOLD)


def line_chart_frame(w=6.4, h=3.5, y0=-0.4):
    """简易折线图框：返回 (框, x轴, y轴, 原点)"""
    org = vec(-w / 2, y0 - h / 2)
    xa = Arrow(org, org + vec(w + 0.25, 0), color=MUTED, stroke_width=3, buff=0,
               max_tip_length_to_length_ratio=0.06)
    ya = Arrow(org, org + vec(0, h + 0.25), color=MUTED, stroke_width=3, buff=0,
               max_tip_length_to_length_ratio=0.06)
    return VGroup(xa, ya), xa, ya, org


def poly_from(points, color, width=6):
    m = VMobject(stroke_color=color, stroke_width=width)
    m.set_points_as_corners([vec(p[0], p[1]) for p in points])
    return m


def ratchet_profiles(w=6.6, teeth=4, rise=0.62, drop=0.30):
    """闪烁棘轮的两条坡：返回 (锯齿坡, 光滑坡, 谷底坐标表)
    锯齿坡整体向右上方倾斜 —— 谷底一个比一个高。"""
    pts, x, y = [], -w / 2, -1.15
    step = w / teeth
    for _ in range(teeth):
        pts.append(vec(x, y))
        pts.append(vec(x + step * 0.76, y + rise))        # 缓升到齿顶
        pts.append(vec(x + step, y + rise - drop))        # 急落成谷
        x += step
        y += rise - drop
    saw = VMobject(stroke_color=GOLD, stroke_width=6)
    saw.set_points_as_corners(pts)
    flat = Line(vec(-w / 2, 0.95), vec(w / 2, -0.95), color=BLUE, stroke_width=6)
    valleys = [pts[3 * i] for i in range(teeth)]
    return saw, flat, valleys


# =====================================================================
# 00 钩子
