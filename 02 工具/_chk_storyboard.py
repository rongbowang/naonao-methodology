# -*- coding: utf-8 -*-
"""_chk_storyboard.py — 06_画面绘制.md 自检（9 项）

用法：
    python "02 工具/_chk_storyboard.py"                 # 默认 NO.20
    python "02 工具/_chk_storyboard.py" NO.21_两扇门

检查项：
  1. 19 项 × N 镜齐全（`### 1.` ~ `### 19.` 各出现 N 次）
  2. 逐句动作表行数 == 该镜句数
  3. 每镜所有 hex 都出现在该镜 §18 颜色清单里
  4. 每条 prompt 以 `no text` 结尾，且不含 number / numbered / letter / digit
  5. 元素清单里的坐标都在 0–1080 × 0–1440 内（出血元素除外，需在该行写明「出血/有意」）
  6. 字卡底边 ≤1104；该镜有 camera 时 ≤990（06_outro 标准模板按 outroStd 固定位置，豁免）
  7. 全文无「中间/旁边/适当/大概/差不多」（台词原文排除）
  8. 与 timeline.json 的句数 / 起止 / 时长逐镜一致
  9. 长镜专项：≥15s 的镜运镜段数 ≥3；NO.21 的 04_solve 动作表 11 行
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPNAME = sys.argv[1] if len(sys.argv) > 1 else "NO.20_住满的旅馆"
EP = os.path.join(ROOT, "30 制作", EPNAME)
DOC = os.path.join(EP, "06_画面绘制.md")

ok_all = True
def rep(no, name, bad, extra=""):
    global ok_all
    if bad:
        ok_all = False
    print(("[PASS] " if not bad else "[FAIL] ") + "%d. %s%s" % (no, name, extra))
    for b in bad[:12]:
        print("        - " + str(b))
    if len(bad) > 12:
        print("        ... 还有 %d 条" % (len(bad) - 12))


txt = open(DOC, encoding="utf-8").read()
tl = json.load(open(os.path.join(EP, "web", "timeline.json"), encoding="utf-8"))
by_id = {s["id"]: s for s in tl["shots"]}

# 台词原文（避免把台词里的「旁边/中间」判成含糊词）
ns = {}
exec(compile(open(os.path.join(EP, "script.py"), encoding="utf-8").read(), "s", "exec"), ns)
ALL_LINES = [ln for sh in ns["SHOTS"] for ln in sh["lines"]]

# ---- 切分镜头小节 ----
parts = re.split(r"(?m)^## (\d+)\. (\d{2}_\w+)", txt)
shots = []          # [(idx, sid, body)]
for i in range(1, len(parts), 3):
    body = parts[i + 2].split("\n## ")[0]
    shots.append((int(parts[i]), parts[i + 1], body))
N = len(shots)

# ---- 1. 19 项齐全 ----
bad = []
for n in range(1, 20):
    c = len(re.findall(r"(?m)^### %d\. " % n, txt))
    if c != N:
        bad.append("`### %d.` 出现 %d 次（应为 %d）" % (n, c, N))
rep(1, "19 项分镜要素齐全（%d 镜）" % N, bad)

# ---- 2. 动作表行数 ----
bad = []
act_rows = {}
for idx, sid, body in shots:
    sec = re.search(r"(?ms)^### 11\. 逐句动作表\n(.*?)^### 12\.", body)
    rows = [l for l in sec.group(1).splitlines() if l.strip().startswith("|")]
    rows = rows[2:] if len(rows) >= 2 else []
    act_rows[sid] = len(rows)
    want = len(by_id[sid]["lines"])
    if len(rows) != want:
        bad.append("%s 动作表 %d 行 / 台词 %d 句" % (sid, len(rows), want))
tot = sum(act_rows.values())
lines_tot = sum(len(s["lines"]) for s in tl["shots"])
if tot != lines_tot:
    bad.append("全片动作表 %d 行 / 台词 %d 句" % (tot, lines_tot))
rep(2, "逐句动作表行数 == 句数（全片 %d 行）" % tot, bad)

# ---- 3. hex 都在 §18 ----
bad = []
for idx, sid, body in shots:
    sec = re.search(r"(?ms)^### 18\. 颜色清单\n(.*?)^### 19\.", body)
    listed = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", sec.group(1)))
    used = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", body))
    miss = sorted(used - listed)
    if miss:
        bad.append("%s 用到但 §18 未列：%s" % (sid, "、".join(miss)))
rep(3, "每镜 hex 全在 §18 清单内", bad)

# ---- 4. prompt ----
bad = []
for idx, sid, body in shots:
    m = re.search(r"(?ms)^### 20\. .*?```\n(.*?)\n```", body)
    if not m:
        bad.append("%s 缺 prompt 代码块" % sid)
        continue
    p = m.group(1).strip()
    if not p.endswith("no text"):
        bad.append("%s prompt 未以 no text 结尾" % sid)
    for w in ["number", "numbered", "letter", "digit"]:
        if re.search(w, p, re.I):
            bad.append("%s prompt 含 %s" % (sid, w))
rep(4, "prompt 全部 no text 收尾且无文字类词", bad)

# ---- 5. 坐标在画内 ----
bad = []
for idx, sid, body in shots:
    sec = re.search(r"(?ms)^### 9\. 元素清单\n(.*?)^### 10\.", body)
    for line in sec.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.match(r"^\d+$", cells[0]):
            continue
        name, coord = cells[1], cells[3]
        if "出血" in coord or "有意出画" in coord:
            continue
        for pair in re.findall(r"\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", coord):
            x, y = int(pair[0]), int(pair[1])
            if x > 1080 or y > 1440:
                bad.append("%s 元素「%s」坐标 (%d,%d) 出画" % (sid, name, x, y))
rep(5, "元素坐标都在 0–1080 × 0–1440 内", bad)

# ---- 6. 字卡安全区 ----
bad = []
for idx, sid, body in shots:
    if sid.endswith("06_outro"):
        continue          # 标准片尾模板 outroStd 固定位置(1032/946)，规范 §四.8 例外
    sec = re.search(r"(?ms)^### 15\. 文字与字卡\n(.*?)^### 16\.", body)
    rows = [l for l in sec.group(1).splitlines() if l.strip().startswith("|")]
    rows = rows[2:] if len(rows) >= 2 else []
    has_cam = len(re.findall(r"(?ms)^### 12\. 运镜", body)) > 0
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        size = int(re.search(r"(\d+)px", cells[1]).group(1)) if re.search(r"(\d+)px", cells[1]) else 30
        m = re.search(r"\((\d+),\s*(\d+)\)", cells[3])
        if not m:
            continue
        y = int(m.group(2))
        bottom = y + size * 0.62
        lim = 990 if has_cam else 1104
        if bottom > lim:
            bad.append("%s 字卡「%s」底边 %.0f > %d" % (sid, cells[0], bottom, lim))
rep(6, "字卡底边 ≤1104（有 camera ≤990）", bad)

# ---- 7. 含糊词 ----
bad = []
scrub = txt
for ln in ALL_LINES:
    scrub = scrub.replace(ln, "")
for w in ["中间", "旁边", "适当", "大概", "差不多"]:
    for m in re.finditer(w, scrub):
        s = max(0, m.start() - 18)
        bad.append("出现「%s」：…%s…" % (w, scrub[s:m.end() + 12].replace("\n", " ")))
rep(7, "全文无「中间/旁边/适当/大概/差不多」（排除台词原文）", bad)

# ---- 8. 与 timeline 一致 ----
bad = []
for idx, sid, body in shots:
    t = by_id[sid]
    m = re.search(r"\*\*([\d.]+)–([\d.]+) s\*\*（([\d.]+) s）　(\d+) 句", body)
    if not m:
        bad.append("%s §1 表头解析失败" % sid)
        continue
    s0, s1, dur, n = float(m.group(1)), float(m.group(2)), float(m.group(3)), int(m.group(4))
    if abs(s0 - t["start"]) > 0.011 or abs(s1 - t["end"]) > 0.011:
        bad.append("%s 起止 %.2f–%.2f vs timeline %.2f–%.2f" % (sid, s0, s1, t["start"], t["end"]))
    if abs(dur - (t["end"] - t["start"])) > 0.02:
        bad.append("%s 时长 %.2f vs %.2f" % (sid, dur, t["end"] - t["start"]))
    if n != len(t["lines"]):
        bad.append("%s 句数 %d vs %d" % (sid, n, len(t["lines"])))
    rows = [l for l in body.splitlines() if re.match(r"^\| \d+ \| [\d.]+–[\d.]+ \|", l)]
    if len(rows) != len(t["lines"]):
        bad.append("%s §1 时间表 %d 行 vs %d 句" % (sid, len(rows), len(t["lines"])))
rep(8, "与 timeline 的句数 / 起止 / 时长逐镜一致", bad)

# ---- 9. 长镜专项 ----
bad = []
for idx, sid, body in shots:
    t = by_id[sid]
    dur = t["end"] - t["start"]
    sec = re.search(r"(?ms)^### 12\. 运镜\n(.*?)^### 13\.", body)
    rows = [l for l in sec.group(1).splitlines() if l.strip().startswith("|")]
    segs = len(rows) - 2 if len(rows) >= 2 else 0
    if dur >= 15 and segs < 3:
        bad.append("%s 时长 %.2fs 只有 %d 段运镜（需 ≥3）" % (sid, dur, segs))
    print("        · %s %.2fs → %d 段运镜" % (sid, dur, segs))
if EPNAME.startswith("NO.21"):
    if act_rows.get("04_solve") != 11:
        bad.append("04_solve 动作表 %s 行（需 11）" % act_rows.get("04_solve"))
rep(9, "≥15s 长镜运镜 ≥3 段" + ("；NO.21 04_solve 动作表 11 行" if EPNAME.startswith("NO.21") else ""), bad)

print()
print("=== %s：%s ===" % (EPNAME, "全绿 ✅" if ok_all else "有 FAIL ❌"))
sys.exit(0 if ok_all else 1)
