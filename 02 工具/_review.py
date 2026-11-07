# -*- coding: utf-8 -*-
"""
_review.py — 文案评审（2026-10-25 新建）

为什么要有它
------------
用户原话（NO.13 退稿）：
  「27 号的视频，你最后那讲的不是重复了吗？一开始说穿蓝外套的打 120，
   后面又说如果是你倒在那儿又要怎么办，感觉你这是把同一套东西讲了两遍。
   这种东西你在写文案的时候检查不出来吗？你写完文案之后是不是应该加一个评级呢？
   加一个评审，评审哪里不好的就改，改了再做视频。」

`check_style.py` 查的是**句子怎么写**（AI 八股、第一人称、节奏）。
它查不出**「同一个解法讲了两遍」**——因为那两遍的单句都合格。

这个脚本查的是**结构**：
  ① 同一个动作在几个镜头里各讲了一遍（例：05 指一个人打 120 / 06 又说指一个人打 120）
  ② 同一个视角词反复出现（例：「换成你」全片 3 次）
  ③ 句与句之间语义撞车（字符 2-gram Jaccard）
  ④ 结尾在复述开头（跨段重复）
  ⑤ 段落因果链：每段的结论有没有成为下一段的问题

用法
----
  python _review.py v13_bystander           # 单期
  python _review.py --all                   # 全量（NO.11 往后的期）
  退出码 0 = 通过
"""
import os
import re
import sys
import json
import argparse
import itertools

from _paths import proj_dir, list_projects   # 期工程目录（新旧兼容）

# ---------------- 动作词表 ----------------
# 一条"动作"= 一组同义词。同一个动作在 >=2 个镜头里出现 = 同一个解法/信息讲了两遍。
ACTIONS = {
    "呼救/打120": ["120", "打电话", "拨电话", "拨打", "报警", "叫救护车", "呼救"],
    "指名/点名": ["指着", "指一个", "点一个", "点名", "指那", "记住名字"],
    "喊/叫": ["喊", "叫住", "大叫"],
    "上前/扶": ["上前", "扶", "冲过去", "走过去"],
    "看/对视": ["眼神", "看着他的眼睛", "看着一个人的眼睛", "对视", "盯"],
    "报告/找人": ["去报告", "找人", "去叫", "拉人"],
}

# 视角/假设词：出现 >=2 次就说明"同一套情景"在反复铺垫
POV = ["换成你", "假如你", "要是你", "如果你", "哪天你", "你站在", "你倒"]

# 句间相似度阈值（字符 2-gram Jaccard）
SIM_SENT = 0.30      # 到这个数就提示
SIM_DUP = 0.80       # 到这个数基本是同一句话 —— FAIL（v42_hotel 有两句 1.00，原来只报了 HINT）
SIM_HEAD_TAIL = 0.22


def load(proj):
    f = os.path.join(proj_dir(proj), "script.py")
    spec_src = open(f, encoding="utf-8").read()
    ns = {}
    exec(compile(spec_src, f, "exec"), ns)
    return ns["SHOTS"]


def bigrams(t):
    t = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def jac(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def review(proj, verbose=True):
    shots = load(proj)
    lines = []          # [(shot_id, idx, text)]
    for sh in shots:
        for i, t in enumerate(sh["lines"]):
            lines.append((sh["id"], i, t))

    fails, warns, hints = [], [], []

    # ① 同一个动作出现在几个镜头
    for name, keys in ACTIONS.items():
        hits = {}
        for sid, _, t in lines:
            for k in keys:
                if k in t:
                    hits.setdefault(sid, []).append(t)
                    break
        if len(hits) >= 2:
            fails.append(("同一动作讲了两遍",
                          f"「{name}」出现在 {len(hits)} 个镜头",
                          [(sid, ts[0]) for sid, ts in hits.items()]))

    # ② 视角词
    pov_hits = {}
    for sid, _, t in lines:
        for k in POV:
            if k in t:
                pov_hits.setdefault(k, []).append(sid)
    for k, sids in pov_hits.items():
        if len(sids) >= 2:
            (fails if len(sids) >= 3 else warns).append(
                ("视角词反复",
                 f"「{k}」· {len(sids)} 次", [(s, k) for s in sids]))

    # ③ 句间语义撞车
    for (s1, i1, t1), (s2, i2, t2) in itertools.combinations(lines, 2):
        if len(t1) < 8 or len(t2) < 8:
            continue
        v = jac(t1, t2)
        if v >= SIM_DUP:
            fails.append(("同一句讲了两遍", f"相似 {v:.2f}",
                          [(s1, t1), (s2, t2)]))
        elif v >= SIM_SENT:
            hints.append(("两句撞车", f"相似 {v:.2f}",
                          [(s1, t1), (s2, t2)]))

    # ④ 结尾复述开头（片尾镜不算）
    body = [s for s in shots if not s["id"].endswith("outro")]
    if len(body) >= 3:
        head = " ".join(body[0]["lines"])
        tail = " ".join(body[-1]["lines"])
        v = jac(head, tail)
        if v >= SIM_HEAD_TAIL:
            fails.append(("结尾复述开头", f"首镜 vs 末镜 相似 {v:.2f}",
                          [(body[0]["id"], body[0]["lines"][0]),
                           (body[-1]["id"], body[-1]["lines"][0])]))

    # ⑤ 因果链：每镜最后一句 vs 下一镜第一句，不该撞车
    for a, b in zip(body, body[1:]):
        v = jac(a["lines"][-1], b["lines"][0])
        if v >= SIM_SENT:
            warns.append(("段落接缝重复", f"{a['id']}→{b['id']} 相似 {v:.2f}",
                          [(a["id"], a["lines"][-1]), (b["id"], b["lines"][0])]))

    res = {"proj": proj, "shots": len(shots), "lines": len(lines),
           "fails": fails, "warns": warns, "hints": hints}
    if verbose:
        print(f"\n=== {proj} · {len(shots)} 镜 / {len(lines)} 句 ===")
        for tag, items, color in (("FAIL", fails, "✗"), ("WARN", warns, "!"),
                                  ("HINT", hints, "·")):
            for name, detail, ev in items:
                print(f"  [{tag}] {name} — {detail}")
                for sid, t in ev:
                    print(f"        {color} {sid}: {t}")
        if not fails and not warns:
            print("  ✅ 结构无重复")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proj", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.all:
        projs = [d for d in list_projects() if re.match(r"NO\.\d+", d)]
    elif a.proj:
        projs = [a.proj]
    else:
        ap.error("给一个工程名，或者 --all")

    bad = 0
    out = []
    for p in projs:
        try:
            r = review(p, verbose=not a.json)
            out.append(r)
            if r["fails"]:
                bad += 1
        except Exception as e:
            print(f"  [skip] {p}: {e}")
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif len(projs) > 1:
        print(f"\n—— {bad}/{len(projs)} 期有 FAIL ——")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
