# -*- coding: utf-8 -*-
"""把各期已生成的 G 版封面改名成终选名，其余版本收进候选归档。

为什么需要单独一个脚本：
    render_all.py 的 cover_one() 里，`_covers.py` 只要版面体检有警告就 rc=2，
    函数直接 return，后面「挑 G 版改名」那段根本不执行 —— 结果封面生成了 15 张
    却没有一张叫「封面_NO.xx_<标题>.png」。这里补上那一段。

用法：
    python "02 工具/_cover_finalize.py"            # 全部 7 期
    python "02 工具/_cover_finalize.py" NO.22 NO.23 # 只处理指定期
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)

EPS = [
    ("NO.17", "NO.17_等一句话", "一百个人等一句话", "2026-10-31", "NO.17_一百个人等一句话"),
    ("NO.18", "NO.18_围一圈报数", "围一圈报数", "2026-11-01", "NO.18_围一圈报数"),
    ("NO.19", "NO.19_地球加长一米", "地球加长一米", "2026-11-02", "NO.19_地球加长一米"),
    ("NO.20", "NO.20_住满的旅馆", "住满的旅馆", "2026-11-03", "NO.20_住满的旅馆"),
    ("NO.21", "NO.21_两扇门", "两扇门", "2026-11-04", "NO.21_两扇门"),
    ("NO.22", "NO.22_少了一格", "少了一格", "2026-11-05", "NO.22_少了一格"),
    ("NO.23", "NO.23_蒙眼分硬币", "蒙眼分硬币", "2026-11-06", "NO.23_蒙眼分硬币"),
]


def finalize(no, ep, short, date, arch, only):
    dirs = [os.path.join(WORK, "30 制作", ep, "30_交付"),
            os.path.join(WORK, "40 出版物", date, arch)]
    box = os.path.join(WORK, "99 归档", "_封面候选_%s" % no.replace(".", ""))
    os.makedirs(box, exist_ok=True)
    ok = True
    for d in dirs:
        if not os.path.isdir(d):
            print("  %s 目录不存在：%s" % (no, d)); ok = False; continue
        cand = [f for f in os.listdir(d) if f.startswith("封面G_")]
        if not cand:
            # 已经改过名了？
            if os.path.exists(os.path.join(d, "封面_%s_%s.png" % (no, short))):
                print("  %s 已是终选名，跳过 %s" % (no, os.path.basename(d))); continue
            print("  %s 没有 G 版：%s" % (no, os.path.basename(d))); ok = False; continue
        pick = {}
        for f in cand:
            if f.endswith("_横版.png"):
                pick[f] = "封面_%s_%s_横版.png" % (no, short)
            elif f.endswith("_16x9.png"):
                pick[f] = "封面_%s_%s_16x9.png" % (no, short)
            elif f.endswith(".png") and "_v" not in f and "_h" not in f and "_w" not in f:
                pick[f] = "封面_%s_%s.png" % (no, short)
        done = []
        for src_name, dst_name in pick.items():
            src = os.path.join(d, src_name)
            dst = os.path.join(d, dst_name)
            if os.path.exists(dst):
                os.rename(dst, dst + ".old")
            os.rename(src, dst)
            done.append(dst_name)
        # 其余候选进归档
        for f in os.listdir(d):
            if f.startswith("封面") and f not in done:
                try:
                    shutil.move(os.path.join(d, f), os.path.join(box, f))
                except Exception:
                    pass
        print("  %s @ %s -> %s" % (no, os.path.basename(d), ", ".join(sorted(done))))
    return ok


def main():
    args = [a for a in sys.argv[1:] if a.startswith("NO.")]
    todo = [e for e in EPS if (not args or e[0] in args)]
    for e in todo:
        finalize(*e, e[0] in args)
    # 校验
    print("\n=== 终选封面核对 ===")
    miss = 0
    for no, ep, short, date, arch in EPS:
        for base, name in ((os.path.join(WORK, "30 制作", ep, "30_交付"), "30_交付"),
                           (os.path.join(WORK, "40 出版物", date, arch), "出版归档")):
            for suf in ("", "_横版", "_16x9"):
                f = os.path.join(base, "封面_%s_%s%s.png" % (no, short, suf))
                if not os.path.exists(f):
                    print("  ✗ 缺 %s/%s%s" % (name, no, suf)); miss += 1
    print("缺失 %d 张" % miss)


if __name__ == "__main__":
    main()
