# -*- coding: utf-8 -*-
"""撤掉我 2026-11-02 误加的 P/S CSS —— 模板里本来就有 P/Q/R/S/T 五个图形版式，
我插在 </style> 前的那段把原有 P 版覆盖了（P 版本来是「上图下文 + 满宽金带压字」）。

同时给 coveru.mjs 补两点：
  · S 版（证物卡）的红印章借 .ebot 渲染，没传 e2 就是空的 → 自动用 num 兜底
  · T 版（数字出血）的 .hero 用 num，没数字就自动隐藏，免得留一个大空格
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _rw import rewrite_file

HTML = os.path.join(HERE, "_webtmpl", "cover_unified.html")
MJS = os.path.join(HERE, "_webtmpl", "coveru.mjs")


def strip_html(s):
    start = s.find("  /* ============================================================\n     2026-11-02 新增两版")
    if start < 0:
        print("  HTML：没找到我加的那段，跳过")
        return s
    end = s.find("body.h.s .sig,body.w.s .sig{color:var(--gold)}", start)
    if end < 0:
        print("  HTML：尾部锚点没找到")
        return s
    end = s.find("\n", end) + 1
    print("  HTML：删除 %d 字符" % (end - start))
    return s[:start] + s[end:]


def patch_mjs(s):
    if "自检：S 版印章兜底" in s:
        print("  MJS：已补过，跳过")
        return s
    old = """    const C = Object.assign({ title: title, sub: sub, chips: chips, num: num, e1: "", e2: "" },
                            SET[v] || {});"""
    new = """    const C = Object.assign({ title: title, sub: sub, chips: chips, num: num, e1: "", e2: "" },
                            SET[v] || {});
    // 自检：S 版印章兜底（.ebot 被借去画红章，没字就是个空圈）
    if (v === "S" && !C.e2) C.e2 = num || "已验";
    if (v === "T" && !C.num) C.num = "?";"""
    if old not in s:
        print("  MJS：锚点没找到")
        return s
    print("  MJS：补 S/T 兜底")
    return s.replace(old, new)


rewrite_file(HTML, strip_html)
rewrite_file(MJS, patch_mjs)
print("  html=%d mjs=%d" % (os.path.getsize(HTML), os.path.getsize(MJS)))
