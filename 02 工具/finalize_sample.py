# -*- coding: utf-8 -*-
"""finalize_sample.py — 两镜样板收尾：收集 sfx.json → 拼片 → 混流

worker 模式渲染不会自动收集音效（只有 capture.mjs 全片模式才收集），
所以这里单独起一次页面调 window.__collectSFX() 写 sfx.json，再拼片混流。
用法：python "02 工具/finalize_sample.py"
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMP = os.path.join(ROOT, "30 制作", "NO.17_等一句话", "sample")
NODE_PATH = "C:/Users/13071/.workbuddy/binaries/node/workspace/node_modules"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("FAIL:", " ".join(cmd)[:160])
        print((r.stderr or r.stdout)[-1200:])
        sys.exit(1)
    return r.stdout


def collect_sfx():
    js = r"""
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');
(async () => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'shell',
    args: ['--headless=new', '--no-sandbox', '--disable-gpu'],
  });
  const p = await b.newPage();
  await p.setViewport({ width: 1080, height: 1440 });
  await p.goto('file:///' + path.resolve('index.html').replace(/\\/g, '/') + '?capture=1',
               { waitUntil: 'load' });
  await p.waitForFunction('window.__ready === true', { timeout: 30000 });
  const list = await p.evaluate('window.__collectSFX()');
  fs.writeFileSync('sfx.json', JSON.stringify(list, null, 1));
  console.log('sfx', list.length);
  await b.close();
})();
"""
    env = dict(os.environ, NODE_PATH=NODE_PATH)
    out = run(["node", "-e", js], cwd=SMP, env=env)
    print("  ", out.strip())


def main():
    tl = json.load(open(os.path.join(SMP, "timeline.json"), encoding="utf-8"))
    frames = round(tl["duration"] * 30)
    print("timeline duration=%.2fs  应为 %d 帧" % (tl["duration"], frames))

    collect_sfx()

    # 拼片（在 _seg 内用相对文件名，绝对 UNC 路径会拼错——2026-11-01 NO.18 踩过）
    segdir = os.path.join(SMP, "_seg")
    segs = sorted([f for f in os.listdir(segdir) if f.startswith("s") and f.endswith(".mp4")],
                  key=lambda x: int(x[1:-4]))
    print("分段:", segs)
    lst = os.path.join(segdir, "list.txt")
    open(lst, "w", encoding="utf-8").write("\n".join("file '%s'" % f for f in segs))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", "../render.mp4"], cwd=segdir)

    n = run(["ffprobe", "-v", "error", "-select_streams", "v",
             "-show_entries", "stream=nb_frames", "-of", "default=nw=1:nk=1",
             "render.mp4"], cwd=SMP).strip()
    print("render.mp4 帧数 =", n, "/", frames, "OK" if str(n) == str(frames) else "⚠ 不符")
    if str(n) != str(frames):
        sys.exit(2)

    # 混流（半写 mux.py：旁白 -20 / BGM 垫 10dB / 音效归一到 -19 再乘 vol / 整体 -18.5）
    out = run([sys.executable, "mux.py", "final.mp4"], cwd=SMP)
    print(out[-900:] if out else "")


if __name__ == "__main__":
    main()
