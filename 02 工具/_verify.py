# -*- coding: utf-8 -*-
r"""_verify.py — 守门脚本：把《02 验收规格》第三节那 5 个「没人管」的缺口变成可执行

它不产生内容，只回答一个问题：**现在的库里，有没有不合规的东西。**

## 用法
    python _verify.py                # 全库体检
    python _verify.py v53_paper      # 单期体检
    python _verify.py --baseline     # 重建「素材只读」基线（第一次跑或故意改过素材后）

## 检查哪 5 件事（对应 02 验收规格 第三节）
1. 期号唯一性      —— 同一 `NO.xx` 不许出现在两处；目录名里的 vNN 要与 NO 对上
2. 交付四件套      —— 40 出版物/<日期>/ 要有 mp4 + 封面×3 + 标题与描述.txt
3. 素材只读        —— 20 素材_只读/ 的 mtime+size 与基线一致
4. 工程与归档一致  —— script.py 比 final.mp4 新 = 改了台词没重渲
5. 立项单          —— 30 制作/<期>/00_立项单.md 在，且首行写着遵循哪版规格

退出码：全过 0，否则 1（可直接用在管线里当闸）
"""
import json
import os
import re
import sys

from _paths import ROOT, WORK, PUB, ASSETS, proj_dir, list_projects

BASE = os.path.join(ASSETS, "_baseline.json")
TOL = 90.0        # mtime 容差（秒）：搬家/同步会造成时间抖动，别为 1 秒报错


# ────────────────────────── 工具
def proj_no(name):
    """从工程目录的 script.py 里读 NO 字段"""
    p = os.path.join(proj_dir(name), "script.py")
    if not os.path.exists(p):
        return None
    m = re.search(r'^NO\s*=\s*"([^"]+)"', open(p, encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def pub_dirs():
    if not os.path.isdir(PUB):
        return []
    return sorted(d for d in os.listdir(PUB)
                  if re.match(r"\d{4}-\d{2}-\d{2}$", d))


# ────────────────────────── 1 期号唯一性
def check_no_unique():
    bad, seen = [], {}
    for name in list_projects():
        no = proj_no(name)
        if not no:
            bad.append("%s 的 script.py 里没有 NO 字段" % name)
            continue
        seen.setdefault(no, []).append("工程:" + name)
        # 目录名必须以 NO.xx 开头，且与 script.py 的 NO 一致（ADR-0001）
        m = re.match(r"(NO\.\d+)", name)
        if not m:
            bad.append("%s 目录名没用 `NO.xx_` 开头（ADR-0001）" % name)
        elif m.group(1) != no:
            bad.append("%s 目录名写着 %s，但 script.py 写的是 %s" % (name, m.group(1), no))

    for d in pub_dirs():
        for f in os.listdir(os.path.join(PUB, d)):
            m = re.match(r"(?:封面_)?(NO\.\d+)", f)
            if m:
                seen.setdefault(m.group(1), []).append("发布:" + d)

    for no, where in sorted(seen.items()):
        if len(set(where)) > 2:      # 工程 1 处 + 发布 1 处 是正常的
            bad.append("%s 出现在 %d 处：%s" % (no, len(set(where)), "、".join(sorted(set(where)))))
    return bad, "%d 个期号" % len(seen)


# ────────────────────────── 2 交付四件套
def check_delivery():
    bad = []
    for d in pub_dirs():
        files = os.listdir(os.path.join(PUB, d))
        mp4 = [f for f in files if f.endswith("_竖屏.mp4")]
        if not mp4:
            bad.append("%s 缺成片 _竖屏.mp4" % d)
            continue
        no = re.match(r"(NO\.\d+)", mp4[0])
        no = no.group(1) if no else "?"
        for suf in ["", "_横版", "_16x9"]:
            hit = [f for f in files if f.startswith("封面_%s_" % no) and f.endswith(suf + ".png")
                   and f.count("_") == ("封面_%s_x" % no).count("_") + (1 if suf else 0)]
            if not hit:
                bad.append("%s 缺封面%s" % (d, suf or "竖版"))
        if not [f for f in files if f.startswith("标题与描述_")]:
            bad.append("%s 缺 标题与描述.txt" % d)
    return bad, "%d 个发布日" % len(pub_dirs())


# ────────────────────────── 3 素材只读
def snap_assets():
    out = {}
    for base, dirs, files in os.walk(ASSETS):
        dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
        for f in files:
            if f.startswith("_"):
                continue
            p = os.path.join(base, f)
            try:
                st = os.stat(p)
                out[os.path.relpath(p, ASSETS)] = [int(st.st_mtime), st.st_size]
            except Exception:
                pass
    return out


def check_assets(baseline=False):
    cur = snap_assets()
    if baseline or not os.path.exists(BASE):
        json.dump(cur, open(BASE, "w", encoding="utf-8"), ensure_ascii=False)
        return [], "建立基线（%d 个文件）" % len(cur)
    old = json.load(open(BASE, encoding="utf-8"))
    bad = []
    for k, v in old.items():
        if k not in cur:
            bad.append("素材被删：%s" % k)
        elif cur[k][1] != v[1]:
            bad.append("素材被改：%s（大小 %d → %d）" % (k, v[1], cur[k][1]))
        elif abs(cur[k][0] - v[0]) > 1:
            bad.append("素材被碰过：%s（mtime 变了）" % k)
    add = [k for k in cur if k not in old]
    for k in add[:10]:
        bad.append("素材区多了文件：%s" % k)
    return bad, "%d 个文件比对" % len(old)


# ────────────────────────── 4 工程与归档一致
def check_sync():
    bad, n = [], 0
    for d in pub_dirs():
        mp4 = [f for f in os.listdir(os.path.join(PUB, d)) if f.endswith("_竖屏.mp4")]
        if not mp4:
            continue
        no = re.match(r"(NO\.\d+)", mp4[0])
        if not no:
            continue
        no = no.group(1)
        t_pub = os.path.getmtime(os.path.join(PUB, d, mp4[0]))
        for name in list_projects():
            if proj_no(name) != no:
                continue
            n += 1
            sp = os.path.join(proj_dir(name), "script.py")
            if os.path.exists(sp) and os.path.getmtime(sp) > t_pub + TOL:
                bad.append("%s：script.py 比已发布的成片新 —— 改了台词没重渲" % no)
            sc = os.path.join(proj_dir(name), "web", "js", "scenes.js")
            if os.path.exists(sc) and os.path.getmtime(sc) > t_pub + TOL:
                bad.append("%s：scenes.js 比成片新 —— 改了画面没重渲" % no)
    return bad, "%d 期比对" % n


# ────────────────────────── 5 立项单
SPEC = os.path.join(ROOT, "00 规格与决策", "01 一期规格.md")


def spec_ver():
    try:
        t = open(SPEC, encoding="utf-8").read()
        m = re.search(r"版本\s*\*\*v([\d.]+)\*\*", t) or re.search(r"^>\s*版本\s*\**v([\d.]+)", t, re.M)
        return "v" + m.group(1) if m else "v?"
    except Exception:
        return "v?"


def check_brief(only=None):
    bad, n = [], 0
    for name in list_projects():
        if only and name != only:
            continue
        n += 1
        p = os.path.join(proj_dir(name), "00_立项单.md")
        if not os.path.exists(p):
            bad.append("%s 没有 00_立项单.md" % name)
            continue
        head = open(p, encoding="utf-8").read()[:300]
        if "遵循" not in head:
            bad.append("%s 的立项单没写「遵循：01 一期规格 vX」" % name)
    return bad, "%d 期（当前规格 %s）" % (n, spec_ver())


# ────────────────────────── 主流程
def main():
    only = None
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if argv:
        only = argv[0]
    baseline = "--baseline" in sys.argv

    tasks = [
        ("期号唯一性", lambda: check_no_unique()),
        ("交付四件套", lambda: check_delivery()),
        ("素材只读", lambda: check_assets(baseline)),
        ("工程与归档一致", lambda: check_sync()),
        ("立项单", lambda: check_brief(only)),
    ]
    total_bad = 0
    print("=" * 62)
    print("_verify  项目根：%s" % ROOT)
    print("=" * 62)
    for label, fn in tasks:
        try:
            bad, info = fn()
        except Exception as e:
            print("\n[%s] 跑挂了：%s" % (label, e))
            total_bad += 1
            continue
        mark = "OK  " if not bad else "FAIL"
        print("\n[%s] %-14s %s" % (mark, label, info))
        for b in bad:
            print("      · %s" % b)
        total_bad += len(bad)

    print("\n" + "=" * 62)
    if total_bad == 0:
        print("全过。可以发。")
    else:
        print("共 %d 处问题。" % total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
