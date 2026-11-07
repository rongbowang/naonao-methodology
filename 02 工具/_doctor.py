# -*- coding: utf-8 -*-
"""_doctor.py — 换机器后的第一步，跑这个。

    python _doctor.py

它只检查、不修改任何东西。全部 OK 之后再去跑生产管线。
"""
import importlib
import os
import shutil
import subprocess
import sys

OK, BAD, WARN = "  [OK]  ", "  [缺]  ", "  [注意]"

problems = []


def head(t):
    print("\n" + t)
    print("-" * 58)


def chk(label, fn, hint="", optional=False):
    try:
        v = fn()
        print("%s %-26s %s" % (OK, label, v))
        return True
    except Exception as e:
        print("%s %-26s %s" % (WARN if optional else BAD, label, e))
        if hint:
            print("         → %s" % hint)
        if not optional:
            problems.append(label)
        return False


# ---------- 1. Python ----------
head("1. Python")
chk("版本", lambda: "%d.%d.%d" % sys.version_info[:3],
    "需要 3.10 以上")
chk("可执行文件", lambda: sys.executable)

# ---------- 2. Python 包 ----------
head("2. Python 包")
PKGS = [
    ("numpy", "numpy", "pip install numpy"),
    ("Pillow", "PIL", "pip install pillow"),
    ("edge-tts", "edge_tts", "pip install edge-tts"),
    ("potracer", "potrace", "pip install potracer"),
    ("opencv", "cv2", "pip install opencv-python-headless"),
]
for label, mod, hint in PKGS:
    chk(label, lambda m=mod: importlib.import_module(m).__name__ + " 可导入", hint)

# ---------- 3. 命令行工具 ----------
head("3. 命令行工具（必须在 PATH 里）")
for exe, hint in [
    ("ffmpeg", "https://www.gyan.dev/ffmpeg/builds/ 下载后把 bin 加进 PATH"),
    ("ffprobe", "同上（ffmpeg 自带）"),
]:
    chk(exe, lambda e=exe: subprocess.run([e, "-version"], capture_output=True,
                                         text=True).stdout.split("\n")[0][:46], hint)

# ---------- 4. Node ----------
head("4. Node（渲染视频要用）")
chk("node", lambda: subprocess.run(["node", "-v"], capture_output=True,
                                   text=True).stdout.strip(),
    "装 Node 18+")
def _pptr():
    """先按默认找，再按 NODE_PATH 找 —— 本机就是靠 NODE_PATH 生效的。"""
    r = subprocess.run(["node", "-e", 'console.log(require.resolve("puppeteer-core"))'],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()[:58]
    np = os.environ.get("NODE_PATH", "")
    if np:
        return "靠 NODE_PATH 生效: " + np[:50]
    raise RuntimeError("没装，也没设 NODE_PATH")
chk("puppeteer-core", _pptr,
    "二选一：\n"
    "           ① 在工程文件的上一级执行  npm i puppeteer-core\n"
    "           ② 设环境变量 NODE_PATH=<已有 node_modules 的路径>\n"
    "         Windows 临时生效：  set NODE_PATH=C:////path////to////node_modules")

# ---------- 5. 浏览器 ----------
head("5. 浏览器（逐帧截图用）")
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
found = [p for p in BROWSERS if os.path.exists(p)]
if found:
    print("%s 找到 %d 个" % (OK, len(found)))
    for p in found:
        print("         %s" % p)
else:
    print("%s 一个都没找到 —— capture.mjs 起不来" % BAD)
    print("         → 装 Chrome 或 Edge")
    problems.append("浏览器")

# ---------- 6. GPU（决定配音方案能走哪条） ----------
head("6. 显卡（决定本地 TTS 能不能跑）")
try:
    r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                        "--format=csv,noheader"], capture_output=True,
                       text=True, timeout=20)
    if r.returncode == 0 and r.stdout.strip():
        print("%s %s" % (OK, r.stdout.strip()))
        print("         → 可以试 CosyVoice2 / IndexTTS2 / F5-TTS 这类本地大模型")
    else:
        raise RuntimeError("没有输出")
except Exception:
    print("%s 没有 NVIDIA 显卡" % WARN)
    print("         → 本地大模型 TTS 不可行，配音只能走 edge / 云端 API")

# ---------- 7. 工程结构 ----------
head("7. 工程结构")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 项目根（每日成果 / 试验片 在这一层）
for d, base in [("_webtmpl", HERE), ("_lib", HERE), ("_webtmpl/js", HERE),
                ("_webtmpl/assets", HERE), ("每日成果", ROOT), ("试验片", ROOT)]:
    p = os.path.join(base, d)
    if os.path.isdir(p):
        print("%s %-26s %s" % (OK, d, p))
    else:
        print("%s %-26s 不存在：%s" % (BAD, d, p))
        problems.append(d)
chk("_lib/tts_edge.py", lambda: "内置，不依赖本机 skill 目录"
    if os.path.exists(os.path.join(HERE, "_lib", "tts_edge.py")) else (_ for _ in ()).throw(
        RuntimeError("缺失")), "从原机器拷过来")

# ---------- 8. 结论 ----------
head("结论")
if problems:
    print("还差 %d 项：%s" % (len(problems), "、".join(problems)))
    print("\n上面每一条都写了怎么装。全绿之后再跑生产管线。")
    sys.exit(1)
else:
    print("全绿。可以开工了 —— 下一步看《交接文档.md》第三节「现在卡在哪」。")
