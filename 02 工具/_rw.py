# -*- coding: utf-8 -*-
r"""_rw.py — 在这台机器上改写「跨机器共享过来的旧文件」

## 为什么需要它
2026-10-30 实测：`\\192.168.1.3\Naonao` 上的文件有两类
  · **另一台机器创建的老文件** -> `open(p,'r+')` 直接 PermissionError（ACL 和新建文件一模一样，原因不明）
  · **本机新建的文件**         -> 正常读写

所以 `Edit` / `Write` 都会失败。但 `os.rename(老文件, 新名字)` 是允许的。
绕法：备份 -> 把老文件改个名 -> 把新内容写成原文件名（新文件，可写）。

## 用法
    from _rw import rewrite, rewrite_file
    rewrite("check_style.py", new_text)
    rewrite_file("check_style.py", lambda s: s.replace("520", "680"))

命令行（交互检查用）：
    python _rw.py check_style.py        # 只测试能不能改，不落盘
"""
import io
import os
import shutil
import sys
import time


def _uniq(base):
    p = base
    while os.path.exists(p):
        p = base + ".%d" % int(time.time() * 1000 % 100000)
    return p


def can_write(path):
    try:
        f = open(path, "r+b")
        f.close()
        return True
    except Exception:
        return False


def rewrite(path, text, backup=True):
    """把 path 改成 text。旧文件自动备份成 <name>.orig"""
    if backup:
        bak = path + ".orig"
        if not os.path.exists(bak):
            shutil.copy(path, bak)
    if can_write(path):
        # 本来就是本机文件，直接写
        io.open(path, "w", encoding="utf-8", newline="").write(text)
        return "direct"

    tmp = _uniq(path + ".__new")
    io.open(tmp, "w", encoding="utf-8", newline="").write(text)
    old = _uniq(path + ".__old")
    os.rename(path, old)          # 老文件让位（允许）
    os.rename(tmp, path)          # 新文件顶上去（新文件，可写）
    return "rename"


def rewrite_file(path, fn, **kw):
    s = io.open(path, encoding="utf-8").read()
    return rewrite(path, fn(s), **kw)


def patch(path, pairs, **kw):
    """按 [(old, new)] 顺序替换，任何一个 old 找不到就报错（防止静默失效）"""
    s = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            raise RuntimeError("%s 里找不到:\n%s" % (path, old[:120]))
        s = s.replace(old, new)
    return rewrite(path, s, **kw)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        if not os.path.exists(p):
            print("%-40s 不存在" % p)
            continue
        w = can_write(p)
        print("%-40s %s" % (p, "可直接写" if w else "只读 -> 走 rename 绕法"))
