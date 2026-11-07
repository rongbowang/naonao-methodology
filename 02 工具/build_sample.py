# -*- coding: utf-8 -*-
"""build_sample.py — 搭 NO.17 两镜样板工程（Phase 1 · 2026-11-01）

在 30 制作/2026-11-01_一百个人等一句话/sample/ 下搭一个独立小工程：
  · 引擎文件从 web/ 拷（index.html 加 assets.js 引用）
  · timeline 只含 00_rule + 04_one；04_one 平移到紧接 00_rule（无缝 = 硬切）
  · voice.wav 按同样区间切拼；sfx.json 由 capture.mjs 全片模式自动收集
用法：python "02 工具/build_sample.py"
"""
import json
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EP = os.path.join(ROOT, "30 制作", "2026-11-01_一百个人等一句话")
WEB = os.path.join(EP, "web")
SMP = os.path.join(EP, "sample")

# 两镜：00_rule 原样；04_one 平移使 start == 00_rule.end（硬切，无 gap）
KEEP = [("00_rule", None), ("04_one", "attach")]

COPY_FILES = ["style.css", "capture.mjs", "_shot.mjs", "_gcheck.mjs", "mux.py"]
COPY_JS = ["kit.js", "lib.js", "assets.js", "engine.js"]


def main():
    os.makedirs(os.path.join(SMP, "js"), exist_ok=True)

    # 1) 引擎文件
    for f in COPY_FILES:
        shutil.copy(os.path.join(WEB, f), os.path.join(SMP, f))
    for f in COPY_JS:
        src = os.path.join(WEB, "js", f)
        if not os.path.exists(src):            # assets.js 等共享资产从模板库取
            src = os.path.join(ROOT, "02 工具", "_webtmpl", "js", f)
        shutil.copy(src, os.path.join(SMP, "js", f))
    # 同步一份回 web/js（全片重画时直接用）
    for f in ("assets.js",):
        dst = os.path.join(WEB, "js", f)
        if not os.path.exists(dst):
            shutil.copy(os.path.join(ROOT, "02 工具", "_webtmpl", "js", f), dst)
    # BGM：优先本期 web/bgm.wav，否则共享库 theme-original（与 NO.17 已发布版同曲）
    bgm_src = os.path.join(WEB, "bgm.wav")
    if not os.path.exists(bgm_src):
        bgm_src = os.path.join(ROOT, "20 素材_只读", "bgm", "theme-original.wav")
    shutil.copy(bgm_src, os.path.join(SMP, "bgm.wav"))

    # index.html：加 assets.js（lib 之后、scenes 之前）
    html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
    if "js/assets.js" not in html:
        html = html.replace('<script src="js/scenes.js"></script>',
                            '<script src="js/assets.js"></script>\n<script src="js/scenes.js"></script>')
    open(os.path.join(SMP, "index.html"), "w", encoding="utf-8").write(html)

    # 2) 两镜 timeline
    tl = json.load(open(os.path.join(WEB, "timeline.json"), encoding="utf-8"))
    by_id = {s["id"]: s for s in tl["shots"]}
    shots = []
    for sid, mode in KEEP:
        s = json.loads(json.dumps(by_id[sid]))
        if mode == "attach":
            shift = shots[-1]["end"] - s["start"]
            s["start"] = round(s["start"] + shift, 3)
            s["end"] = round(s["end"] + shift, 3)
            for ln in s["lines"]:
                ln["g0"] = round(ln["g0"] + shift, 3)
                ln["g1"] = round(ln["g1"] + shift, 3)
                for c in ln["chars"]:
                    c["t0"] = round(c["t0"] + shift, 3)
                    c["t1"] = round(c["t1"] + shift, 3)
        shots.append(s)
    duration = round(shots[-1]["end"] + 1.2, 3)
    out = {"fps": 30, "width": 1080, "height": 1440, "duration": duration,
           "title": tl["title"], "subtitle": tl["subtitle"], "no": tl["no"],
           "shots": shots}
    json.dump(out, open(os.path.join(SMP, "timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(SMP, "timeline.js"), "w", encoding="utf-8").write(
        "window.TIMELINE=" + json.dumps(out, ensure_ascii=False) + ";")
    print("timeline: %d 镜  duration=%.2fs" % (len(shots), duration))
    for s in shots:
        print("  %s  %.2f-%.2f" % (s["id"], s["start"], s["end"]))
        n_sfx = sum(len(ln.get("sfx", [])) for ln in s["lines"])
        print("    sfx 点数 =", n_sfx)

    # 3) voice.wav 切拼（与 timeline 完全一致的区间）
    src = os.path.join(WEB, "voice.wav")
    a0, a1 = 0.0, shots[0]["end"]
    b0 = by_id["04_one"]["start"]
    b1 = by_id["04_one"]["start"] + (shots[1]["end"] - shots[1]["start"]) + 0.15
    fc = ("[0:a]atrim=0:%.3f,asetpts=PTS-STARTPTS[v0];"
          "[0:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS[v1];"
          "[v0][v1]concat=n=2:v=0:a=1" % (a1, b0, b1))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                    "-filter_complex", fc, "-ar", "44100", "-ac", "1",
                    os.path.join(SMP, "voice.wav")], check=True)
    print("voice.wav 切拼完成")


if __name__ == "__main__":
    main()
