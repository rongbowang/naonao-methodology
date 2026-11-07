# -*- coding: utf-8 -*-
"""_humanize.py —— 口播稿「AI 味」体检（本项目口径）

为什么还要一个，跟 check_style 不重复：
  · `check_style.py` 查的是**禁词**（引导语、假对比、编排话、第一人称感受），
    它管"这句话能不能说"。
  · 这个脚本查的是**腔调**：排比太工整、结尾强行升华、每句都在解释、
    全篇没有一个具体锚点、节奏像节拍器。它管"这话像不像人说的"。
  · 通用工具（buhang-humanizer 的 ai-taint-score.js）只认"首先/其次/综上所述"，
    对中文口播基本打 0 分 —— 我们这两期就是 0 分却满屏 AI 味，所以另写一套。

用法：
    python "02 工具/_humanize.py" "30 制作/2026-11-05_两扇门/script.py"
    python "02 工具/_humanize.py" <路径> --verbose

评分（0~10，越低越像人写的；目标 ≤3）：
    对称排比 每处 +1.2   强行升华 每处 +1.5   解释腔 每处 +0.8
    无具体锚点 +2.0      零口语毛边 +1.5     节奏均质 +1.5
退出码：0 = 通过（≤4），1 = 需要回炉。
"""
import importlib.util
import os
import re
import statistics
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")

# ① 对称排比：一X…一Y / 都…都 / 有…有 —— 人写东西懒得这么工整
PARALLEL = [
    re.compile(r"一[^，。；]{1,6}[，、]\s*一[^，。；]{1,6}"),
    re.compile(r"[^，。；]{1,6}都[^，。；]{1,8}[，、]\s*[^，。；]{1,6}都"),
    re.compile(r"不是[^，。]{1,10}[，、]\s*(而)?是[^，。]{1,10}"),
    re.compile(r"既[^，。]{1,8}[，、]\s*又[^，。]{1,8}"),
]

# ② 强行升华（口播里最出戏的一种）
GRAND = ["人生巅峰", "意义", "这才是", "证明了", "让我们", "从此", "这一刻",
         "不由得", "不得不", "值得每个人", "真正的"]

# ③ 解释腔：句子在给观众补课，而不是讲事
EXPLAIN = ["也就是说", "换句话说", "这意味着", "两种都成立", "这说明", "等于说",
           "由此可见", "本质上", "说到底"]

# ④ 具体锚点：数字 / 时间 / 器物 —— 有锚点才像真的见过
#
# ★ 2026-11-04 补词表（NO.22 吃亏吃出来的）：
#   原来只认「级/扇/个/天/步/年/秒/次/遍/米」，实物量词一个都没有，
#   于是通篇「八格见方 / 剪两刀 / 四块纸 / 十三格」的稿子被判"没有具体锚点"——
#   工具错，不是稿子错。同理 THINGS 只收了石洞戏的道具（石门/火把/台阶），
#   桌面戏的方格纸、剪刀、直尺、头发全不在里面。
#   加「两」：口语说"两刀""两块"远多于"二刀""二块"，原表直接把最常见的写法漏了。
ANCHOR = re.compile(
    r"\d+|[一二三四五六七八九十百千万两]{1,3}"
    r"(级|扇|个|天|步|年|秒|次|遍|米|格|块|刀|张|条|根|行|层|片|排|把|支)"
)
THINGS = [
    # 洞穴 / 故事戏
    "石门", "火把", "台阶", "洞", "影子", "号牌", "抽屉",
    # 人的身体
    "手", "呼吸", "眼睛",
    # 桌面 / 纸戏
    "方格纸", "纸", "格子", "剪刀", "尺子", "长条", "头发", "缝", "光",
]

# ⑤ 口语毛边
ORAL = ["偏偏", "愣是", "差一点", "就这", "回头", "其实", "吗", "呢", "吧", "啊",
        "说不定", "干脆", "合着", "反正", "谁知道", "——"]


def load(path):
    spec = importlib.util.spec_from_file_location("m", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lines, shots = [], []
    for sh in mod.SHOTS:
        shots.append((sh["id"], list(sh["lines"])))
        lines += list(sh["lines"])
    ok = getattr(mod, "HUMANIZE_OK", []) or []
    return lines, shots, ok


def clean(s):
    return "".join(CJK.findall(s))


def clauses(line):
    return [c for c in re.split(r"[，。；：？！、,;:!?]", line) if clean(c)]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    verbose = "--verbose" in sys.argv
    lines, shots, ok = load(path)

    score = 0.0
    hits = {"parallel": [], "grand": [], "explain": [], "anchor": 0, "oral": 0}

    for ln in lines:
        for pat in PARALLEL:
            for m in pat.finditer(ln):
                # 用户点名要求保留的陈述句（比如谜题本身的"一扇通向公主，一扇通向牢房"）
                if any(o and o in m.group(0) for o in ok):
                    continue
                hits["parallel"].append(m.group(0))
        for w in GRAND:
            if w in ln and not any(w in o for o in ok):
                hits["grand"].append((w, ln))
        for w in EXPLAIN:
            if ln.startswith(w) or ("，" + w) in ln or ("。" + w) in ln or ln.endswith(w):
                hits["explain"].append((w, ln))
    text = "".join(lines)
    hits["anchor"] = len(ANCHOR.findall(text)) + sum(1 for t in THINGS if t in text)
    hits["oral"] = sum(text.count(w) for w in ORAL)

    # 节奏
    cl = [len(clean(c)) for ln in lines for c in clauses(ln)]
    sd = statistics.pstdev(cl) if len(cl) > 1 else 99
    run = best = 0
    for n in cl:
        run = run + 1 if 5 <= n <= 10 else 0
        best = max(best, run)

    if hits["parallel"]:
        score += 1.2 * len(hits["parallel"])
    if hits["grand"]:
        score += 1.5 * len(hits["grand"])
    if hits["explain"]:
        score += 0.8 * len(hits["explain"])
    if hits["anchor"] < 6:
        score += 2.0
    if hits["oral"] < 3:
        score += 1.5
    if best >= 6 or sd < 2.6:
        score += 1.5
    score = min(10, round(score, 1))

    print("口播 AI 味体检 · %s" % os.path.basename(os.path.dirname(path)))
    print("  句数 %d · 字数 %d · 小句 %d · 句长标准差 %.1f · 最长匀速段 %d 小句"
          % (len(lines), sum(len(clean(l)) for l in lines), len(cl), sd, best))
    print("  具体锚点 %d 处 · 口语毛边 %d 处" % (hits["anchor"], hits["oral"]))
    if hits["parallel"]:
        print("  ⚠ 对称排比 %d 处：%s" % (len(hits["parallel"]), " / ".join(hits["parallel"][:4])))
    if hits["grand"]:
        print("  ⚠ 强行升华 %d 处：%s" % (len(hits["grand"]),
              " / ".join(w for w, _ in hits["grand"][:4])))
    if hits["explain"]:
        print("  ⚠ 解释腔 %d 处：%s" % (len(hits["explain"]),
              " / ".join("%s｜%s" % (w, l[:14]) for w, l in hits["explain"][:3])))
    if best >= 6:
        print("  ⚠ 连续 %d 个小句都在 5~10 字，像节拍器" % best)
    if hits["anchor"] < 6:
        print("  ⚠ 具体锚点不足（<6）：没有一个看得见的东西，观众记不住")
    if hits["oral"] < 3:
        print("  ⚠ 口语毛边不足（<3）：全篇没有「偏偏」「差一点」「呢」「吧」这种活人痕迹")

    print("  AI 味浓度：%.1f / 10  %s" % (score, "（合格 ≤4）" if score <= 4 else "（需回炉 >4）"))
    if verbose:
        for sid, ls in shots:
            print("  [%s] %d 句" % (sid, len(ls)))
    return 0 if score <= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
