# -*- coding: utf-8 -*-
"""自检：9 条提示词是否齐全、自包含、期号自洽。"""
import glob, os

D = os.path.dirname(os.path.abspath(__file__))
fs = sorted(glob.glob(os.path.join(D, "NO.*.txt")))
NEED = [
    "交接_2026-11-06.md", "MEMORY.md", "SKILL.md", "用户写法规范.md", "文案规则.md",
    "设定自洽清单.md", "先上网调研", "把最终剧本全文逐句贴到对话框", "贴完就停",
    "05_剧本_送审.md", "_pause.py", "check_style.py", "_humanize.py", "_review.py",
    "_outro.py", "GAP = 0", "_ALL.wav", "_vcheck.py", "封面候选", "抽帧",
    "不要问我问题", "至少 20 个",
]
print("TXT 数量", len(fs))
bad = 0
for f in fs:
    s = open(f, encoding="utf-8").read()
    no = os.path.basename(f).split("_")[0]
    miss = [k for k in NEED if k not in s]
    checks = {
        "only_this_ep": ("只做这一期：" + no) in s,
        "outro_no": ('outroStd({no:"' + no + '"})') in s,
        "eng_dir": ("30 制作/2026-11-" in s),
        "wait_review": "等我说「可以」" in s,
        "no_publish": "不许碰 `40 出版物/`" in s,
    }
    fails = miss + [k for k, v in checks.items() if not v]
    print(("OK   " if not fails else "FAIL "), no, "字数", len(s), "" if not fails else "缺:" + ",".join(fails))
    if fails:
        bad += 1
md = os.path.join(D, "00_全部提示词.md")
h = os.path.join(D, "窗口提示词_2026-11.html")
mdtxt = open(md, encoding="utf-8").read()
htxt = open(h, encoding="utf-8").read()
print("合订 MD 期号数", mdtxt.count("\n## NO."), "HTML textarea 数", htxt.count("<textarea"), "复制按钮数", htxt.count('class="cp"'))
print("FAIL 总数", bad + (0 if mdtxt.count("\n## NO.") == 9 and htxt.count("<textarea") == 9 and htxt.count('class="cp"') == 9 else 1))
