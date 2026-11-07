# -*- coding: utf-8 -*-
"""比对「画面文字」与「旁白字幕」的重复度。
画面文字取 scenes.js 里 K.chip / chip / K.txt / bigNum 的字符串，
旁白取 script.py 的 SHOTS[*].lines。
报告相似度 >= 阈值的配对，供人工判断是否重复。
"""
import io, os, re, sys, glob, difflib

sys.stdout.reconfigure(encoding="utf-8")

STOP = set("的了是在也就能把被和与或就这那一个不有")


def norm(s):
    return re.sub(r"[\s，。、；：？！·\-—…「」“”‘’（）()]+", "", s)


def load_lines(script):
    ns = {}
    exec(compile(io.open(script, encoding="utf-8").read(), script, "exec"), ns)
    out = []
    for sh in ns["SHOTS"]:
        for ln in sh["lines"]:
            out.append(ln)
    return out


def load_pic_texts(scenes):
    src = io.open(scenes, encoding="utf-8").read()
    # 抓 chip(...) 与 K.txt(...) 与 bigNum(...) 里的第一个/第二个字符串字面量
    pats = [
        r"(?:K\.)?chip\(\s*(?:root|svg|\w+)\s*,\s*\"([^\"]+)\"",
        r"K\.txt\([^,]+,\s*\"([^\"]+)\"",
        r"bigNum\(\s*(?:root|\w+)\s*,\s*\"([^\"]+)\"",
    ]
    got = []
    for p in pats:
        got += re.findall(p, src)
    # 去重保序
    seen, res = set(), []
    for g in got:
        g = g.strip()
        if not g or g in seen:
            continue
        seen.add(g)
        res.append(g)
    return res


def ratio(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    # 子串包含直接判高
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def scan(proj, th=0.55):
    script = os.path.join(proj, "script.py")
    scenes = os.path.join(proj, "web/js/scenes.js")
    if not (os.path.exists(script) and os.path.exists(scenes)):
        print("跳过", proj)
        return
    lines = load_lines(script)
    pics = load_pic_texts(scenes)
    hits = []
    for p in pics:
        if len(norm(p)) < 6:      # 太短的标签（如「片药」）跳过
            continue
        best, bl = 0.0, ""
        for l in lines:
            r = ratio(p, l)
            if r > best:
                best, bl = r, l
        if best >= th:
            hits.append((best, p, bl))
    print("=" * 66)
    print(os.path.basename(proj), " 画面文字", len(pics), "条，疑似重复", len(hits), "条")
    for best, p, bl in sorted(hits, reverse=True):
        print("  %.2f  画面: %s" % (best, p))
        print("        字幕: %s" % bl)
    if not hits:
        print("  ✅ 无重复")


if __name__ == "__main__":
    from _paths import proj_dir, list_projects
    args = sys.argv[1:]
    if not args:
        args = list_projects()          # 默认扫全部期（新旧命名都认）
    for a in args:
        a = a.rstrip("/")
        scan(a if os.path.isdir(a) else proj_dir(a))
