# -*- coding: utf-8 -*-
"""
竖屏 9:16 科普视频公共样式 / 布局 / 工具
画布: frame_width=9, frame_height=16  ->  x∈[-4.5,4.5], y∈[-8,8]
"""
import numpy as np
from manim import *

# ---------------- 画布 ----------------
FRAME_W, FRAME_H = 9.0, 12.0          # 3:4 竖屏
config.frame_width = FRAME_W
config.frame_height = FRAME_H
config.background_color = "#0A1A2F"

# ---------------- 布局锚点（frame 9x12: x∈[-4.5,4.5], y∈[-6,6]） ----------------
TITLE_Y = 4.5        # 主标题
TAG_Y = 3.85         # 副标题 / 章节标签
MAIN_TOP = 3.2       # 主画面上界
MAIN_Y = 0.6         # 主画面中心
MAIN_BOT = -2.2      # 主画面下界
NOTE_Y = -2.9        # 数值 / 注释行
NOTE2_Y = -3.5       # 第二注释行
SAFE_BOT = -4.1      # 字幕安全区（不要放元素）

# ---------------- 配色 ----------------
BG = "#0A1A2F"
BLUE = "#4A9EFF"
CYAN = "#5FD8E8"
GOLD = "#FFC857"
CORAL = "#FF6B6B"
INK = "#E8F1FF"
MUTED = "#8FA8C8"
GREEN = "#5FD88A"
PURPLE = "#A88CFF"
WHITE = "#FFFFFF"

FONT = "Source Han Sans CN"


def T(txt, size=36, color=INK, weight=NORMAL, slant=NORMAL):
    """中文文字"""
    return Text(txt, font=FONT, font_size=size, color=color,
                weight=weight, slant=slant)


def vec(x, y):
    return np.array([float(x), float(y), 0.0])


def pol(r, th):
    """极坐标 -> 向量"""
    return np.array([r * np.cos(th), r * np.sin(th), 0.0])


# ---------------- 场景骨架 ----------------
def chapter(self, title, tag=None, run_time=1.0):
    """顶部标题条；返回 (title_mob, tag_mob)"""
    t = T(title, size=44, color=INK, weight=BOLD).move_to(vec(0, TITLE_Y))
    self.play(Write(t), run_time=run_time)
    tg = None
    if tag:
        tg = T(tag, size=28, color=MUTED).move_to(vec(0, TAG_Y))
        self.play(FadeIn(tg), run_time=run_time * 0.5)
    return t, tg


def hint(self, txt, y=NOTE_Y, size=30, color=GOLD, run_time=0.9):
    m = T(txt, size=size, color=color).move_to(vec(0, y))
    self.play(FadeIn(m), run_time=run_time)
    return m


def bar_chart(values, labels, width=6.4, height=3.4, colors=None,
              gap=0.28, label_size=26, show_value=True, value_fmt="%.0f%%"):
    """竖排柱状图，返回 VGroup（已居中于原点，需自行 move_to）"""
    colors = colors or [BLUE] * len(values)
    n = len(values)
    bw = (width - gap * (n - 1)) / n
    vmax = max(values) if max(values) > 0 else 1
    g = VGroup()
    for i, (v, lab) in enumerate(zip(values, labels)):
        h = height * v / vmax
        x = -width / 2 + bw / 2 + i * (bw + gap)
        rect = Rectangle(width=bw, height=max(h, 0.001), fill_color=colors[i],
                         fill_opacity=0.85, stroke_width=0)
        rect.move_to(vec(x, -height / 2 + h / 2))
        g.add(rect)
        lb = T(lab, size=label_size, color=MUTED).move_to(vec(x, -height / 2 - 0.3))
        g.add(lb)
        if show_value:
            vt = T(value_fmt % v, size=label_size, color=colors[i]
                   ).move_to(vec(x, -height / 2 + h + 0.28))
            g.add(vt)
    return g


def axis_frame(x_range, y_range, width=6.6, height=3.6,
               x_label="", y_label="", color=MUTED, tick_size=20):
    """简易坐标框（不用 LaTeX 的 NumberLine）"""
    ax = VGroup()
    base = Rectangle(width=width, height=height, stroke_color=color,
                     stroke_width=2, fill_opacity=0)
    ax.add(base)
    if x_label:
        ax.add(T(x_label, size=22, color=color).next_to(base, DOWN, buff=0.22))
    if y_label:
        ax.add(T(y_label, size=22, color=color).next_to(base, LEFT, buff=0.22))
    return ax


# ---------------- 时间预算 ----------------
def fill_beats(self, beats, sid=None):
    """把场景时长补齐到节拍总长"""
    total = sum(beats) if sid is None else sum(beats[sid])
    rest = total - self.renderer.time
    if rest > 0.05:
        self.wait(rest)


def beat_fill(self, dur, t0):
    """补齐到某个节拍的结束时刻"""
    rest = dur - (self.renderer.time - t0)
    if rest > 0.03:
        self.wait(rest)


def clear_all(self, rt=0.5):
    mobs = [m for m in self.mobjects]
    if mobs:
        self.play(*[FadeOut(m) for m in mobs], run_time=rt)


# ---------------- 针 / 通用图形 ----------------
def make_needle(length=4.0, color=INK, thick=7, tip=0.16):
    """两端带端点的线段"""
    line = Line(vec(-length / 2, 0), vec(length / 2, 0),
                color=color, stroke_width=thick)
    d1 = Dot(vec(-length / 2, 0), color=CYAN, radius=tip)
    d2 = Dot(vec(length / 2, 0), color=CORAL, radius=tip)
    return VGroup(line, d1, d2)


def set_needle(nd, a, b):
    """把针放到 a->b"""
    nd[0].put_start_and_end_on(a, b)
    nd[1].move_to(a)
    nd[2].move_to(b)
    return nd


def sector_setup(center, radius, start_angle, color=BLUE, opacity=0.4):
    """可生长的扇形：返回 (mobject, ValueTracker)"""
    def mk(a):
        return Sector(radius=radius, start_angle=start_angle, angle=max(a, 1e-4),
                      fill_color=color, fill_opacity=opacity,
                      stroke_width=0).shift(center)
    sec = mk(1e-4)
    vt = ValueTracker(1e-4)
    sec.add_updater(lambda m: m.become(mk(vt.get_value())))
    return sec, vt


def rounded_panel(width=7.4, height=4.6, color=BLUE, opacity=0.10, stroke=1.2):
    return RoundedRectangle(width=width, height=height, corner_radius=0.25,
                            fill_color=color, fill_opacity=opacity,
                            stroke_color=color, stroke_width=stroke,
                            stroke_opacity=0.35)


# =====================================================================
# 品牌固定件（所有视频复用；每期一字不改）
# =====================================================================
BRAND_NAME = "思维模型"
PANEL = "#132C4E"


def make_badge(radius=1.1, color=GOLD, lw=6):
    """六边形金属徽章 —— 视觉签名"""
    halo = RegularPolygon(n=6, radius=radius * 1.42, start_angle=90 * DEGREES,
                          stroke_color=color, stroke_width=1.6,
                          stroke_opacity=0.20, fill_opacity=0)
    outer = RegularPolygon(n=6, radius=radius, start_angle=90 * DEGREES,
                           stroke_color=color, stroke_width=lw, fill_opacity=0)
    inner = RegularPolygon(n=6, radius=radius * 0.56, start_angle=90 * DEGREES,
                           stroke_color=color, stroke_width=lw * 0.38, fill_opacity=0)
    core = Dot(radius=radius * 0.1, color=color)
    return VGroup(halo, outer, inner, core)


def brand_signature(self, rt=1.8, no="NO.01"):
    """片头固定签名段：徽章「扣入」-> 品牌词 -> 编号 -> 收缩为顶部页眉常驻。
    返回页眉 VGroup（徽章 + 编号），可留给后续画面使用。"""
    badge = make_badge(1.1).move_to(vec(0, 1.0))
    badge.save_state()
    badge.scale(2.8).rotate(-18 * DEGREES).set_opacity(0)
    self.play(Restore(badge), run_time=rt * 0.42, rate_func=rush_into)

    tag = T(BRAND_NAME, size=44, color=INK, weight=BOLD).move_to(vec(0, -1.7))
    num = T(no, size=34, color=GOLD, weight=BOLD).move_to(vec(0, -2.7))
    self.play(FadeIn(tag, shift=UP * 0.25), run_time=rt * 0.24)
    self.play(FadeIn(num, shift=UP * 0.2), run_time=rt * 0.16)

    small = T(no, size=22, color=GOLD, weight=BOLD).move_to(vec(0.05, 6.5))
    self.play(badge.animate.scale(0.30).move_to(vec(-1.05, 6.5)),
              FadeOut(tag),
              ReplacementTransform(num, small),
              run_time=rt * 0.30)
    return VGroup(badge, small)


def envelope(w=1.15, h=0.78, color=INK, sw=2.4):
    """信封道具"""
    body = RoundedRectangle(width=w, height=h, corner_radius=0.06,
                            stroke_color=color, stroke_width=sw, fill_opacity=0)
    mid = body.get_center() + DOWN * h * 0.20
    flap = VGroup(Line(body.get_corner(UL), mid, color=color, stroke_width=sw),
                  Line(body.get_corner(UR), mid, color=color, stroke_width=sw))
    return VGroup(body, flap)


def red_cross(w=0.9, h=0.9, color=CORAL, sw=7):
    """红叉"""
    return VGroup(Line(vec(-w / 2, h / 2), vec(w / 2, -h / 2),
                       color=color, stroke_width=sw),
                  Line(vec(-w / 2, -h / 2), vec(w / 2, h / 2),
                       color=color, stroke_width=sw))


def check_mark(size=0.9, color=GREEN, sw=9):
    """对勾"""
    return VGroup(Line(vec(-size * 0.45, size * 0.05), vec(-size * 0.12, -size * 0.32),
                       color=color, stroke_width=sw),
                  Line(vec(-size * 0.12, -size * 0.32), vec(size * 0.48, size * 0.35),
                       color=color, stroke_width=sw))


# =====================================================================
# 简笔画图标库 —— 「能用图就不用文字」
# 设计原则：
#   · 全部用基础图元拼，返回 VGroup，以原点为中心，可整体 scale()
#   · 侧视统一朝一个方向，方便并排； limb 用粗线 + 圆头，呈手绘简笔画质感
#   · 颜色只传主色，内部自动派生明暗（同一色系 + 透明度）
# =====================================================================

def draw_car(color=GOLD, scale=1.0):
    """小汽车（侧面，朝右）"""
    g = VGroup()
    g.add(RoundedRectangle(width=1.72, height=0.46, corner_radius=0.17,
                           fill_color=color, fill_opacity=0.92, stroke_width=0))
    g.add(Polygon(vec(-0.60, 0.23), vec(-0.30, 0.68), vec(0.44, 0.68), vec(0.70, 0.23),
                  fill_color=color, fill_opacity=0.70, stroke_width=0))
    g.add(Polygon(vec(-0.47, 0.27), vec(-0.28, 0.60), vec(0.38, 0.60), vec(0.57, 0.27),
                  fill_color=BG, fill_opacity=0.88, stroke_width=0))
    for x in (-0.50, 0.54):
        g.add(Dot(radius=0.21, color=INK, fill_opacity=0.95).move_to(vec(x, -0.24)))
        g.add(Dot(radius=0.085, color=color).move_to(vec(x, -0.24)))
    g.scale(scale)
    return g


def draw_goat(color=MUTED, scale=1.0, horn_c=None):
    """山羊（侧面，朝左）：身体 + 头 + 弯角 + 四腿 + 尾"""
    horn_c = horn_c or INK
    g = VGroup()
    g.add(Ellipse(width=1.20, height=0.58, fill_color=color, fill_opacity=0.90,
                  stroke_width=0).move_to(vec(0.20, 0.04)))
    g.add(Polygon(vec(-0.26, 0.24), vec(-0.62, 0.46), vec(-0.58, 0.10), vec(-0.18, 0.02),
                  fill_color=color, fill_opacity=0.90, stroke_width=0))
    g.add(Ellipse(width=0.44, height=0.52, fill_color=color, fill_opacity=0.95,
                  stroke_width=0).move_to(vec(-0.84, 0.34)))
    g.add(Ellipse(width=0.26, height=0.20, fill_color=color, fill_opacity=0.95,
                  stroke_width=0).move_to(vec(-1.04, 0.20)))
    g.add(Ellipse(width=0.22, height=0.11, fill_color=color, fill_opacity=0.95,
                  stroke_width=0).move_to(vec(-0.66, 0.60)).rotate(0.45))
    for dx in (-0.80, -0.98):
        g.add(Arc(radius=0.17, start_angle=95 * DEGREES, angle=110 * DEGREES,
                  color=horn_c, stroke_width=6).move_to(vec(dx, 0.62)))
    for x in (-0.28, -0.06, 0.36, 0.58):
        g.add(Line(vec(x, -0.24), vec(x, -0.78), color=color, stroke_width=7))
    g.add(Line(vec(0.80, 0.14), vec(1.04, 0.46), color=color, stroke_width=6))
    g.scale(scale)
    return g


def draw_person(color=INK, scale=1.0, long_hair=False, mic=False,
                glasses=False, hair_color=None):
    """人物简笔画（正面站立）"""
    hair_color = hair_color or color
    g = VGroup()
    g.add(RoundedRectangle(width=0.68, height=1.02, corner_radius=0.30,
                           fill_color=color, fill_opacity=0.82, stroke_width=0)
          .move_to(vec(0, -0.06)))
    g.add(Circle(radius=0.27, stroke_color=color, stroke_width=6, fill_opacity=0)
          .move_to(vec(0, 0.76)))
    g.add(Arc(radius=0.285, start_angle=16 * DEGREES, angle=148 * DEGREES,
              color=hair_color, stroke_width=9).move_to(vec(0, 0.76)))
    if long_hair:
        g.add(Line(vec(-0.26, 0.82), vec(-0.34, 0.02), color=hair_color, stroke_width=9))
        g.add(Line(vec(0.26, 0.82), vec(0.34, 0.02), color=hair_color, stroke_width=9))
    g.add(Line(vec(-0.34, 0.26), vec(-0.58, -0.32), color=color, stroke_width=7))
    g.add(Line(vec(0.34, 0.26), vec(0.58, -0.32), color=color, stroke_width=7))
    g.add(Line(vec(-0.17, -0.58), vec(-0.22, -1.26), color=color, stroke_width=7))
    g.add(Line(vec(0.17, -0.58), vec(0.22, -1.26), color=color, stroke_width=7))
    if glasses:
        g.add(Circle(radius=0.10, stroke_color=CYAN, stroke_width=2.6, fill_opacity=0)
              .move_to(vec(-0.11, 0.78)))
        g.add(Circle(radius=0.10, stroke_color=CYAN, stroke_width=2.6, fill_opacity=0)
              .move_to(vec(0.11, 0.78)))
        g.add(Line(vec(-0.01, 0.78), vec(0.01, 0.78), color=CYAN, stroke_width=2.6))
    if mic:
        g.add(Line(vec(0.58, -0.26), vec(0.36, 0.54), color=color, stroke_width=6))
        g.add(RoundedRectangle(width=0.17, height=0.28, corner_radius=0.08,
                               fill_color=GOLD, fill_opacity=0.95, stroke_width=0)
              .move_to(vec(0.31, 0.66)))
    g.scale(scale)
    return g


def draw_host(scale=1.0):
    """主持人：紫人物 + 话筒 + 领结"""
    p = draw_person(color=PURPLE, scale=scale, mic=True)
    bt = VGroup(
        Polygon(vec(-0.16, 0.42), vec(0.16, 0.42), vec(0.0, 0.30),
                fill_color=GOLD, fill_opacity=0.95, stroke_width=0),
        Polygon(vec(-0.16, 0.30), vec(0.16, 0.30), vec(0.0, 0.42),
                fill_color=GOLD, fill_opacity=0.95, stroke_width=0),
    )
    p.add(bt)
    return p


def draw_bulb(color=GOLD, scale=1.0):
    """灯泡（想通了 / 灵感）"""
    g = VGroup()
    g.add(Circle(radius=0.36, stroke_color=color, stroke_width=6,
                 fill_color=color, fill_opacity=0.12).move_to(vec(0, 0.16)))
    g.add(RoundedRectangle(width=0.30, height=0.20, corner_radius=0.05,
                           fill_color=color, fill_opacity=0.85, stroke_width=0)
          .move_to(vec(0, -0.34)))
    g.add(Arc(radius=0.15, start_angle=200 * DEGREES, angle=140 * DEGREES,
              color=color, stroke_width=4).move_to(vec(0, 0.16)))
    for a in (28, 90, 152):
        g.add(Line(pol(0.55, a * DEGREES), pol(0.76, a * DEGREES),
                   color=color, stroke_width=4))
    g.scale(scale)
    return g


def draw_letters(n=4, color=MUTED, scale=1.0, spread=0.15):
    """一摞信（读者来信）"""
    g = VGroup()
    for i in range(n):
        e = envelope(1.02, 0.70, color=color, sw=2.6)
        e.rotate((i - (n - 1) / 2) * 1.1 * DEGREES)
        e.move_to(vec((i - (n - 1) / 2) * spread * 0.35,
                      (i - (n - 1) / 2) * spread))
        g.add(e)
    g.scale(scale)
    return g


def draw_pie(frac, color=GREEN, r=1.0, track_color=MUTED, scale=1.0):
    """占比圆饼：frac 份量着色，其余为浅色轨道"""
    g = VGroup()
    g.add(Sector(radius=r, angle=TAU, start_angle=0, fill_color=track_color,
                 fill_opacity=0.16, stroke_width=0))
    g.add(Sector(radius=r, angle=TAU * max(frac, 1e-3), start_angle=90 * DEGREES,
                 fill_color=color, fill_opacity=0.90, stroke_width=0))
    g.scale(scale)
    return g


# ---------------- 通用精致构件（从项目场景上提，供所有视频复用） ----------------
def title_bar(self, txt, size=42, y=TITLE_Y, color=INK, rt=0.42):
    """统一标题：文字 + 下方金色短线"""
    t = T(txt, size=size, color=color, weight=BOLD).move_to(vec(0, y))
    ul = Line(vec(-0.85, 0), vec(0.85, 0), color=GOLD, stroke_width=4).move_to(vec(0, y - 0.62))
    self.play(Write(t), run_time=rt)
    self.play(GrowFromCenter(ul), run_time=rt * 0.55)
    return VGroup(t, ul)


def fancy_door(num, w=2.0, h=2.7, color=BLUE, num_size=42, solid=False):
    """带内框 + 把手的门；solid=True 为关死状态（不透视门后奖品）"""
    outer = RoundedRectangle(width=w, height=h, corner_radius=0.10,
                             fill_color=color,
                             fill_opacity=0.92 if solid else 0.15,
                             stroke_color=color, stroke_width=3.5)
    inner = RoundedRectangle(width=w - 0.36, height=h - 0.36, corner_radius=0.06,
                             stroke_color=color, stroke_width=1.2,
                             stroke_opacity=0.40, fill_opacity=0)
    inner.move_to(outer.get_center())
    handle = Dot(radius=0.06, color=color).move_to(
        outer.get_corner(DR) + LEFT * 0.30 + UP * 0.34)
    numt = T(str(num), size=num_size, color=INK, weight=BOLD
             ).move_to(outer.get_center() + UP * 0.10)
    return VGroup(outer, inner, handle, numt)


def open_door(self, door, content, rt=0.7):
    """开门：门体淡出，露出门后的奖品图标"""
    content.move_to(door[0].get_center())
    self.play(door[0].animate.set_opacity(0.05),
              door[1].animate.set_stroke(opacity=0.0),
              FadeOut(door[2]), FadeOut(door[3]),
              FadeIn(content, scale=0.6), run_time=rt)


def chip(txt, color=MUTED, size=24):
    """小标签（带圆角底衬）"""
    t = T(txt, size=size, color=color, weight=BOLD)
    box = RoundedRectangle(width=t.width + 0.42, height=t.height + 0.26,
                           corner_radius=0.12,
                           fill_color=color, fill_opacity=0.12,
                           stroke_color=color, stroke_width=1.4,
                           stroke_opacity=0.5)
    box.move_to(t.get_center())
    return VGroup(box, t)


def prize_icon(kind, scale=1.0):
    """奖品图标：车 / 羊 —— 一律用图，不用文字"""
    return draw_car(scale=scale) if kind == "car" else draw_goat(scale=scale)


def note_line(self, txt, y=NOTE_Y, size=28, color=INK, rt=0.55):
    m = T(txt, size=size, color=color).move_to(vec(0, y))
    self.play(FadeIn(m, shift=UP * 0.15), run_time=rt)
    return m


def scorpion_icon(color=CORAL, scale=1.0, tail_len=1.0):
    """蝎子简笔：身体 + 一对大钳 + 四对足 + 上翘分节毒尾。
    返回 (整体, 尾部分组) —— 尾部可单独高亮 / 单独淡出（表现断尾）"""
    body = Ellipse(width=1.00, height=0.52, fill_color=color, fill_opacity=0.92,
                   stroke_width=0).move_to(vec(0.10, 0))
    claws = VGroup()
    for dy in (0.30, -0.30):
        claws.add(ArcBetweenPoints(vec(-0.40, 0.10 * np.sign(dy)), vec(-0.92, dy),
                                   angle=0.5, color=color, stroke_width=5))
        claws.add(Circle(radius=0.13, fill_color=color, fill_opacity=0.92,
                         stroke_width=0).move_to(vec(-0.98, dy)))
    legs = VGroup()
    for i in range(4):
        x = -0.20 + i * 0.26
        legs.add(Line(vec(x, -0.20), vec(x - 0.13, -0.46), color=color, stroke_width=4))
        legs.add(Line(vec(x, 0.20), vec(x - 0.13, 0.46), color=color, stroke_width=4))
    tail = VGroup()
    pts = [vec(0.62, 0.06), vec(0.90, 0.30), vec(1.02, 0.66), vec(0.88, 1.00)]
    for i in range(len(pts) - 1):
        tail.add(Line(pts[i], pts[i + 1], color=color, stroke_width=5))
    tail.add(Line(pts[-1], pts[-1] + vec(-0.03, 0.26), color=color, stroke_width=5))
    tail.add(Dot(radius=0.10, color=color).move_to(vec(0.85, 1.28)))
    g = VGroup(body, claws, legs, tail)
    g.scale(scale)
    return g, tail


def wheel_icon(color=GOLD, scale=1.0, spokes=8):
    """轮子：外圈 + 辐条 + 花鼓 + 轮缘亮点。返回 (整体, 可旋转部分)"""
    R = 1.10
    rim = Circle(radius=R, stroke_color=color, stroke_width=6, fill_opacity=0)
    hub = Circle(radius=0.17, fill_color=color, fill_opacity=0.9, stroke_width=0)
    sp = VGroup(*[Line(pol(R * 0.18, k * TAU / spokes), pol(R * 0.94, k * TAU / spokes),
                       color=color, stroke_width=3) for k in range(spokes)])
    dot = Dot(radius=0.14, color=CORAL).move_to(pol(R, -PI / 2))
    spin = VGroup(sp, dot)
    g = VGroup(rim, spin, hub)
    g.scale(scale)
    return g, spin


# =====================================================================
# 音画同步三件套（2026-10-17）：seq_play / idle_* / 姿态人物
# 背景：此前手写 run_time + beat_fill(self.wait) 导致成片 79.5% 是静止帧
# =====================================================================
def seq_play(scene, steps, dur, min_rt=0.05):
    """把一段时长 dur 按权重依次分给多个动画 —— **总时长严格等于 dur，不留静止帧**。

    steps: [(anims, weight), ...]，anims 是可传给 scene.play 的对象元组
        seq_play(self, [([Create(line)], 0.6), ([FadeIn(lab)], 0.4)], b[1])
    替代「self.play(..., run_time=0.8) + beat_fill(...)」的写法。
    """
    tot = max(sum(max(s[1], 1e-6) for s in steps), 1e-6)
    left = float(dur)
    n = len(steps)
    for i, step in enumerate(steps):
        anims, w = step[0], step[1]
        rf = step[2] if len(step) > 2 else None
        rt = left if i == n - 1 else float(dur) * max(w, 1e-6) / tot
        rt = max(rt, min_rt)
        args = list(anims) if isinstance(anims, (list, tuple)) else [anims]
        if rf is not None:
            scene.play(*args, run_time=rt, rate_func=rf)
        else:
            scene.play(*args, run_time=rt)
        left -= rt


def idle_breath(mob, amp=0.025, period=1.5):
    """常驻呼吸微动（高度轻微起伏）—— 需要「停一下」时用它代替 self.wait"""
    st = {"t": 0.0, "h": mob.height}

    def _upd(m, dt):
        st["t"] += dt
        m.set_height(max(st["h"] * (1 + amp * np.sin(TAU * st["t"] / period)), 1e-4))
    mob.add_updater(_upd)
    return mob


def idle_float(mob, amp=0.07, period=1.9):
    """常驻缓慢浮动 —— 让静止画面保持活气"""
    c0 = mob.get_center()
    st = {"t": 0.0}

    def _upd(m, dt):
        st["t"] += dt
        m.move_to(c0 + vec(0, amp * np.sin(TAU * st["t"] / period)))
    mob.add_updater(_upd)
    return mob


def idle_roll(path, period=2.8, color=CORAL, radius=0.13, start=0.0):
    """**常驻滚动小球**：沿给定路径匀速循环滚动。

    用途：让画面在任何时段都有运动 —— 尤其是「旁白在讲、主体没动作」的空档。
    path 不需要真的加进场景（只用来取点），小球自己加进去即可。
    """
    d = Dot(radius=radius, color=color)
    st = {"t": start}

    def _upd(m, dt):
        st["t"] = (st["t"] + dt / max(period, 1e-3)) % 1.0
        m.move_to(path.point_from_proportion(st["t"]))
    d.add_updater(_upd)
    return d


def idle_spin(mob, period=3.0, about=None):
    """常驻缓慢自转（用于轮子、齿轮、时钟指针）"""
    st = {"t": 0.0}
    p = about if about is not None else mob.get_center()

    def _upd(m, dt):
        st["t"] += dt
        m.rotate(TAU * dt / period, about_point=p)
    mob.add_updater(_upd)
    return mob


def get_hand(color=INK, scale=1.0):
    """一只手（掌心 + 三指 + 拇指）—— 用于「抓住直线把它拽弯」这类动作"""
    palm = Circle(radius=0.20, fill_color=color, fill_opacity=0.95, stroke_width=0)
    fingers = VGroup(*[RoundedRectangle(
        width=0.095, height=0.27, corner_radius=0.045,
        fill_color=color, fill_opacity=0.95, stroke_width=0
    ).move_to(vec(-0.11 + i * 0.11, 0.25)) for i in range(3)])
    thumb = RoundedRectangle(width=0.095, height=0.23, corner_radius=0.045,
                             fill_color=color, fill_opacity=0.95,
                             stroke_width=0).move_to(vec(0.22, 0.08)).rotate(-0.7)
    g = VGroup(fingers, thumb, palm)
    g.scale(scale)
    return g


def draw_person_desk(color=INK, scale=1.0, lamp=True):
    """**伏案工作的人**：上身前倾、双臂压桌、头低垂；桌上纸笔 + 一盏灯。
    返回 (整体, 笔) —— 笔可加抖动做「一直在写」的微动。"""
    desk = Line(vec(-1.10, -0.42), vec(1.10, -0.42), color=MUTED, stroke_width=6)
    torso = Line(vec(0.46, -0.42), vec(0.10, 0.58), color=color, stroke_width=10)
    arm1 = Line(vec(0.16, 0.48), vec(-0.62, -0.36), color=color, stroke_width=6)
    arm2 = Line(vec(0.16, 0.38), vec(-0.46, -0.36), color=color, stroke_width=6)
    head = Circle(radius=0.20, fill_color=color, fill_opacity=0.95,
                  stroke_width=0).move_to(vec(0.04, 0.76))
    paper = Rectangle(width=0.66, height=0.06, fill_color=INK, fill_opacity=0.75,
                      stroke_width=0).move_to(vec(-0.62, -0.38))
    quill = Line(vec(-0.72, -0.34), vec(-0.50, 0.10), color=GOLD, stroke_width=4)
    parts = [desk, paper, quill, torso, arm1, arm2, head]
    if lamp:
        pole = Line(vec(1.10, -0.42), vec(1.10, 0.70), color=MUTED, stroke_width=4)
        shade = ArcBetweenPoints(vec(1.10, 0.70), vec(0.60, 0.66), angle=0.9,
                                 color=GOLD, stroke_width=5)
        glow = Circle(radius=0.18, fill_color=GOLD, fill_opacity=0.45,
                      stroke_width=0).move_to(vec(0.52, 0.62))
        parts += [pole, shade, glow]
    g = VGroup(*parts)
    g.scale(scale)
    return g, quill


def draw_speaker(color=CYAN, scale=1.0):
    """**正在讲话的人**：身体 + 会开合的嘴。返回 (整体, 嘴)。
    场景里给嘴加一个 set_height 的正弦 updater 即可「一直说个不停」。"""
    body = RoundedRectangle(width=0.54, height=0.74, corner_radius=0.20,
                            fill_color=color, fill_opacity=0.90,
                            stroke_width=0).move_to(vec(0, 0.26))
    head = Circle(radius=0.29, fill_color=color, fill_opacity=0.95,
                  stroke_width=0).move_to(vec(0, 0.98))
    mouth = Ellipse(width=0.20, height=0.05, fill_color=BG, fill_opacity=0.95,
                    stroke_width=0).move_to(vec(0, 0.93))
    g = VGroup(body, head, mouth)
    g.scale(scale)
    return g, mouth


def talk_updater(mouth, base=0.05, amp=0.14, period=0.30, phase=0.0):
    """给 draw_speaker 的嘴加开合动画（直接用 add_updater 挂上即可）"""
    st = {"t": phase}

    def _upd(m, dt):
        st["t"] += dt
        m.set_height(max(base + amp * abs(np.sin(TAU * st["t"] / period)), 1e-3))
    mouth.add_updater(_upd)
    return mouth


def bubble(text=None, color=CYAN, w=0.50, h=0.34, tail=True):
    """对话气泡（可选文字；不写字就只用形状表示「有人在说话」）"""
    b = RoundedRectangle(width=w, height=h, corner_radius=0.12,
                         fill_color=color, fill_opacity=0.18,
                         stroke_color=color, stroke_width=1.6)
    g = VGroup(b)
    if tail:
        g.add(Polygon(vec(-0.10, -h / 2), vec(0.10, -h / 2), vec(-0.02, -h / 2 - 0.16),
                      fill_color=color, fill_opacity=0.18,
                      stroke_color=color, stroke_width=1.6))
    if text:
        g.add(T(text, size=22, color=color).move_to(b.get_center()))
    return g
