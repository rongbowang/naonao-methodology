"""_covers.py — 每期一次性产出 5 版 × 3 比例 = 15 张封面候选，并自动体检。

为什么要有这个脚本：
    封面文案（数字 / 一句话 / 大字词）是创作决定，不能自动编；
    但「5 版 × 竖 1080×1440 / 横 1440×1080 / 16:9 1920×1080」这 15 张的
    渲染、命名、越界检查、对比度检查全是重复劳动，必须一键完成。

用法：
    python _covers.py v17_sloth                 # 自动找归档日期，输出到 每日成果/<date>/封面候选
    python _covers.py v17_sloth --out D:/xxx    # 指定输出目录
    python _covers.py v17_sloth --check         # 只体检，不渲染
    python _covers.py v17_sloth --only 3        # 只渲某一版（调排版时用）

每期需要一个 工程文件/<proj>/covers.json：
    {
      "no":   "NO.17",                      // 期号，缺省从 v17 推
      "slug": "为了一次拉屎",                // 文件名用，缺省 = TITLE
      "sub":  "树懒 · 下树排便",             // 副标题 / 说明
      "num":  "50%",                        // v4 巨数字（没有强数字就留空，v4 会被跳过）
      "cap":  "树懒死于下树的路上",           // 一句话结论
      "word": "赌上命",                      // v3 中间那句（建议 2~4 字）
      "en":   "50% DIE ON THE GROUND"       // v5 英文小标
    }
缺字段时的降级：sub→SUBTITLE，cap→TITLE，word→TITLE 前 4 字，num→""。
"""
import json, os, re, subprocess, sys, glob, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
from _paths import WORK, PUB   # 期工程 / 归档容器
TMPL = os.path.join(ROOT, "_webtmpl")
ARCH = PUB
NODE = "C:/Users/13071/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
NODE_ENV = {"NODE_PATH": "C:/Users/13071/.workbuddy/binaries/node/workspace/node_modules"}
PY = sys.executable


def read_script(proj):
    """从 script.py 里取 TITLE / SUBTITLE（不 import，避免副作用）"""
    f = os.path.join(WORK, proj, "script.py")
    out = {"TITLE": "", "SUBTITLE": ""}
    if not os.path.exists(f):
        return out
    s = open(f, encoding="utf-8").read()
    for k in out:
        m = re.search(r'^%s\s*=\s*["\'](.+?)["\']' % k, s, re.M)
        if m:
            out[k] = m.group(1)
    return out


def find_archive_dir(no):
    """按期号反查归档目录（文件名以 NO.XX_ 开头）"""
    for d in sorted(glob.glob(os.path.join(ARCH, "2026-*"))):
        if glob.glob(os.path.join(d, "%s_*.mp4" % no)):
            return d
    return None


def build_params(proj):
    meta = read_script(proj)
    cfg = {}
    cf = os.path.join(WORK, proj, "covers.json")
    if os.path.exists(cf):
        cfg = json.load(open(cf, encoding="utf-8"))
    m = re.match(r"v(\d+)", os.path.basename(proj))
    no = cfg.get("no") or ("NO.%02d" % int(m.group(1)) if m else "NO.00")
    # 封面大字 ≠ 视频标题：script.py 里的 TITLE 常是完整问句（12 字，必爆版面），
    # 封面用 covers.json 的 title（4~8 字短标题），没写就退回 slug
    title = cfg.get("title") or cfg.get("slug") or meta["TITLE"] or "标题待填"
    sub = cfg.get("sub") or meta["SUBTITLE"] or title
    cap = cfg.get("cap") or title
    word = cfg.get("word") or title[:4]
    num = cfg.get("num", "")
    return {
        "no": no, "title": title, "slug": cfg.get("slug") or title,
        "sub": sub, "cap": cap, "word": word, "num": num,
        # 统一配色版式要的「红绿胶囊」：用 "|" 分隔，前缀 - 红 / + 绿 / 其余青
        "chips": cfg.get("chips") or cap or word,
        # 图形 key：见 _webtmpl/js/cover_arts.js。缺省 sloth 只是兜底
        "art": cfg.get("art") or "sloth",
        # 四个版式各自的文案（JSON 字符串）。没写就用上面那套公用文案
        "set": json.dumps(cfg.get("variants") or {}, ensure_ascii=False),
    }


def C_arg():
    return "--slug"


def run(cmd, env=None, quiet=True):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=e)
    if r.returncode != 0:
        print("  [失败] %s" % " ".join(cmd[1:3]))
        print((r.stderr or r.stdout)[-1200:])
    return r


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    proj = args[0]
    out = None
    check_only = "--check" in args
    only = args[args.index("--only") + 1] if "--only" in args else ""
    if "--out" in args:
        out = args[args.index("--out") + 1]

    P = build_params(proj)
    if not out:
        d = find_archive_dir(P["no"])
        out = os.path.join(d, "封面候选") if d else os.path.join(WORK, proj, "web", "out", "covers")

    print("=== %s  %s" % (P["no"], P["title"]))
    print("    竖版 1080×1440 / 横版 1440×1080 / 16:9 1920×1080，共 5 版 = 15 张")
    print("    num=%r  chips=%r  art=%s  slug=%s" % (P["num"], P["chips"], P["art"], P["slug"]))
    if not P["num"]:
        print("    [注] 没给 num，F 版的大数字会空着")
    print("    -> %s" % os.path.abspath(out))

    # 2026-10-24 修：漏了 --slug 会让文件名全变成「封面A_NO.12_封面.png」；
    # --cap / --word 是旧 5 版式的参数，统一配色版式不认，去掉免得混淆
    common = ["--no", P["no"], "--title", P["title"], C_arg(), P["slug"],
              "--sub", P["sub"], "--num", P["num"],
              "--chips", P["chips"], "--art", P["art"], "--set", P["set"],
              # ★ 必须显式传 --only：_uchek.mjs 默认是 "ABCD"，
              #   而 C / D 两版式 2026-10-24 已删除（CSS 里没有 body.c / body.d），
              #   不传就会去查两个不存在的版式，报出 70 处假越界。
              "--only", "ABEFGPQRST"]

    if not check_only:
        os.makedirs(out, exist_ok=True)
        cmd = [NODE, os.path.join(TMPL, "coveru.mjs")] + common + ["--out", out, "--modes", "vhw", "--only", "ABEFGPQRST"]
        if only:
            cmd += ["--only", only]
        r = run(cmd, NODE_ENV)
        n = len(glob.glob(os.path.join(out, "*.png")))
        print("\n[1/3] 渲染完成：%d 张（4 版式 × 3 比例）" % n)
        if n < 15 and not only:
            print("  ⚠ 少于 15 张，检查上一步报错")

    # --- 版面体检 ---
    print("\n[2/3] 版面体检（越界 / 互压 / 字号 / 信息点）")
    r = run([NODE, os.path.join(TMPL, "_uchek.mjs")] + common, NODE_ENV)
    txt = "\n".join(l for l in r.stdout.splitlines() if not l.startswith("[diag]"))
    bad = txt.count("⚠")
    print(txt.strip())
    print("\n  → %s" % ("✅ 版面干净" if bad == 0 else "⚠ %d 处需修（见上）" % bad))

    # --- 对比度体检 ---
    print("\n[3/3] 对比度体检（明暗跨度 / 空白块 / 缩略可读）")
    if os.path.isdir(out):
        r = run([PY, os.path.join(ROOT, "_cvqa.py"), out])
        print(r.stdout.strip()[-1800:])
    else:
        print("  （目录不存在，跳过）")

    warnings = sum(1 for l in txt.splitlines() if "⚠" in l)
    if warnings:
        print("\n提示：版面有 %d 处警告，通常是文案太长（cap/sub 超过 9 字）或标题超过 6 字。"
              % warnings)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
