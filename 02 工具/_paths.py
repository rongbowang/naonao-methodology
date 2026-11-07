# -*- coding: utf-8 -*-
r"""_paths.py — 目录重构期的路径解析（旧位置、新位置都找得到）

## 为什么要有这个文件
2026-10-31 把 190 个条目从 `工程文件/` 平铺改成编号目录（见 00 规格与决策/ADR）。
脚本里写死了 `工程文件/<期>` 和 `每日成果/`，一搬就全废。

这个模块把「找东西」集中到一处，并且**两套位置都试**：
    先找新位置（30 制作 / 40 出版物 / 20 素材_只读 / 99 归档）
    找不到再退回旧位置（工程文件 / 每日成果）
所以**搬到一半也不会挂**，可以分批迁。

## 用法
    from _paths import ROOT, WORK, PUB, ARC, ASSETS, proj_dir

    ROOT      项目根（含「00 规格与决策」的那一层）
    WORK      期工程容器
    PUB       发布归档容器
    ARC       历史归档
    ASSETS    只读素材
    proj_dir("v53_paper")   某期的工程目录（新旧都能找到）
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_root(start):
    """往上找含「00 规格与决策」的那一层；找不到就退回上一级"""
    p = start
    for _ in range(8):
        if os.path.isdir(os.path.join(p, "00 规格与决策")):
            return p
        up = os.path.dirname(p)
        if up == p:
            break
        p = up
    return os.path.dirname(start)


def _pick(*cands):
    """返回第一个存在的；都不存在就返回最后一个（报错信息更有用）"""
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[-1]


ROOT = _find_root(HERE)

def _count_projects(base):
    if not os.path.isdir(base):
        return 0
    return sum(1 for d in os.listdir(base)
               if os.path.exists(os.path.join(base, d, "script.py")))


# 期工程：新 `30 制作` / 旧 `工程文件`。哪边真的有期就指向哪边（搬迁期两边都在时取多的）
_NEW, _OLD = os.path.join(ROOT, "30 制作"), os.path.join(ROOT, "工程文件")
WORK = _NEW if _count_projects(_NEW) >= _count_projects(_OLD) and _count_projects(_NEW) > 0 else _OLD
# 发布归档：新 `40 出版物` / 旧 `每日成果`
PUB = _pick(os.path.join(ROOT, "40 出版物"), os.path.join(ROOT, "每日成果"))
# 历史归档
ARC = _pick(os.path.join(ROOT, "99 归档"), os.path.join(ROOT, "每日成果"))
# 只读素材：新 `20 素材_只读` / 旧 `工程文件/assets`
ASSETS = _pick(os.path.join(ROOT, "20 素材_只读"), os.path.join(HERE, "assets"))
# 工具/模板
TOOLS = HERE
TMPL = _pick(os.path.join(HERE, "_webtmpl"), os.path.join(ROOT, "02 工具", "_webtmpl"))


def proj_dir(name):
    """某期的工程目录。名字可以带也可以不带路径，只给目录名就行。"""
    return _pick(os.path.join(WORK, name),
                 os.path.join(ROOT, "工程文件", name))


def list_projects():
    """列出所有期工程的目录名（新旧位置合并，去重）"""
    seen, out = set(), []
    for base in (WORK, os.path.join(ROOT, "工程文件")):
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base)):
            if d in seen:
                continue
            if os.path.exists(os.path.join(base, d, "script.py")):
                seen.add(d)
                out.append(d)
    return out


if __name__ == "__main__":
    print("ROOT  ", ROOT)
    print("WORK  ", WORK)
    print("PUB   ", PUB)
    print("ARC   ", ARC)
    print("ASSETS", ASSETS)
    print("TMPL  ", TMPL)
    print("期工程 %d 个" % len(list_projects()))
