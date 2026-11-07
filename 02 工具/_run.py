# -*- coding: utf-8 -*-
r"""_run.py — 一条命令跑完一期的渲染链（避免管道截断/SIGPIPE 把人坑掉）

之前用 `python gen_timeline.py | head -1` 会在 head 读够一行就关闭管道，
gen_timeline 被 SIGPIPE 打断，timeline.json 根本没写出来，后面全崩。
这个脚本用 subprocess + 落盘日志，不用管道。

用法:
    python _run.py v52_rope2                # 全链路（含重新合成配音）
    python _run.py v52_rope2 --no-tts       # 跳过配音，只重渲（台词没改时用这个，省 40 秒）
    python _run.py v52_rope2 --no-prep      # 不挪产物（第一次跑、产物还不存在时）
"""
import os
import subprocess
import sys

from _paths import WORK

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/13071/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
NODE = r"C:/Users/13071/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
NODE_PATH = r"C:/Users/13071/.workbuddy/binaries/node/workspace/node_modules"
LOG = os.path.join(os.environ.get("TEMP", "/tmp"), "run_logs")


def step(name, args, cwd, env=None):
    os.makedirs(LOG, exist_ok=True)
    lp = os.path.join(LOG, name + ".log")
    e = dict(os.environ)
    if env:
        e.update(env)
    with open(lp, "w", encoding="utf-8", errors="replace") as f:
        r = subprocess.run(args, cwd=cwd, env=e, stdout=f, stderr=subprocess.STDOUT)
    tail = ""
    try:
        lines = [x for x in open(lp, encoding="utf-8", errors="replace").read().splitlines() if x.strip()]
        tail = lines[-1] if lines else ""
    except Exception:
        pass
    print("  [%s] exit=%d  %s" % (name, r.returncode, tail[:110]))
    if r.returncode != 0:
        print("      日志:", lp)
        sys.exit(1)


def main():
    proj = sys.argv[1]
    no_tts = "--no-tts" in sys.argv
    no_prep = "--no-prep" in sys.argv
    pdir = os.path.join(WORK, proj)
    wdir = os.path.join(pdir, "web")
    print("[run]", proj, "(no-tts)" if no_tts else "")

    if not no_prep:
        step("prep", [PY, "_prep.py", proj], ROOT)
        if no_tts:
            # 只重渲也要让 render/final/_seg/out 先让位
            pass
    step("cues", [PY, "gen_cues.py", proj], ROOT)
    if not no_tts:
        step("tts", [PY, "tts_whole.py", "--mode", "all", "--out", "audio", "--fresh"], pdir)
    step("timeline", [PY, "gen_timeline.py"], wdir)
    step("voice", [PY, "build_voice.py"], wdir)
    step("capture", [NODE, "capture.mjs", "--par", "6"], wdir, {"NODE_PATH": NODE_PATH})
    step("mux", [PY, "mux.py"], wdir)
    print("  DONE", proj)


if __name__ == "__main__":
    main()
