# -*- coding: utf-8 -*-
"""_smoke.py — 冒烟测试：证明 TTS + 转码 + 渲染这三条链真的能跑。

    python _smoke.py

`_doctor.py` 查的是「装了没有」，这个查的是「装的东西能不能串起来干活」。
只写临时文件到 系统临时目录，不动工程。
"""
import asyncio
import os
import subprocess
import sys
import tempfile

FAIL = 0


def step(name):
    print("\n[%s]" % name)


def ok(msg):
    print("   OK   %s" % msg)


def bad(msg, fix=""):
    global FAIL
    FAIL += 1
    print("   失败 %s" % msg)
    if fix:
        print("        → %s" % fix)


TMP = tempfile.mkdtemp(prefix="smoke_")
print("临时目录：", TMP)

# ---------- 1. edge-tts 能不能合成 ----------
step("1. edge-tts 合成一句中文")
try:
    import edge_tts

    async def gen():
        c = edge_tts.Communicate("这是一句测试，用来确认配音能不能用。",
                                 "zh-CN-YunyangNeural", rate="+8%")
        await c.save(os.path.join(TMP, "t.mp3"))
    asyncio.run(gen())
    sz = os.path.getsize(os.path.join(TMP, "t.mp3"))
    if sz > 3000:
        ok("生成 %d 字节（联网正常）" % sz)
    else:
        bad("文件只有 %d 字节" % sz, "多半是网络问题，或该地区访问不到微软的语音接口")
except Exception as e:
    bad(repr(e), "pip install edge-tts；确认能访问 speech.platform.bing.com")

# ---------- 2. ffmpeg 转码 ----------
step("2. ffmpeg 转 wav + 读时长")
try:
    wav = os.path.join(TMP, "t.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                    os.path.join(TMP, "t.mp3"), "-ar", "24000", "-ac", "1", wav],
                   check=True)
    import wave
    with wave.open(wav, "rb") as w:
        dur = w.getnframes() / w.getframerate()
    ok("转码成功，时长 %.2fs" % dur)
    if dur < 1.0:
        bad("时长异常短", "检查 ffmpeg 版本")
except FileNotFoundError:
    bad("找不到 ffmpeg", "装 ffmpeg 并加进 PATH")
except Exception as e:
    bad(repr(e))

# ---------- 3. 静音切分（配音方案的关键能力） ----------
step("3. 静音切分（判断整段合成后能不能切出句子边界）")
try:
    import numpy as np
    import edge_tts

    SENT = "第一句话在这里。第二句稍微长一点，中间有个逗号。第三句结束。"

    async def gen2():
        await edge_tts.Communicate(SENT, "zh-CN-YunyangNeural", rate="+0%").save(
            os.path.join(TMP, "s.mp3"))
    asyncio.run(gen2())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(TMP, "s.mp3"),
                    "-ar", "24000", "-ac", "1", os.path.join(TMP, "s.wav")], check=True)
    import wave
    with wave.open(os.path.join(TMP, "s.wav"), "rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16
                          ).astype(np.float32) / 32768.
        sr = w.getframerate()
    hop = int(sr * 0.02)
    n = len(y) // hop
    e = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    sil = e < e.max() * 0.03
    gaps, st = [], None
    for i, s in enumerate(sil):
        if s and st is None:
            st = i
        elif not s and st is not None:
            if (i - st) * 0.02 >= 0.45:      # 句号级停顿阈值
                gaps.append((i - st) * 0.02)
            st = None
    ok("检出 %d 个句号级停顿（这段话有 2 个句号）" % len(gaps))
    if len(gaps) < 2:
        bad("切不出句子边界", "阈值可能要按这台机器的 TTS 版本微调（当前 0.45s）")
except Exception as e:
    bad(repr(e))

# ---------- 4. 浏览器渲染 ----------
step("4. puppeteer + 浏览器 截一帧")
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
    probe = os.path.join(TMP, "_probe.mjs")
    open(probe, "w", encoding="utf-8").write(r'''
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
const cands = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
];
const exe = cands.find(p => fs.existsSync(p));
if (!exe) { console.log("NO_BROWSER"); process.exit(2); }
const b = await puppeteer.launch({ executablePath: exe, headless: "shell",
  args: ["--no-sandbox", "--disable-gpu"] });
const p = await b.newPage();
await p.setViewport({ width: 400, height: 300 });
await p.setContent("<body style='background:#0A1A2F;color:#FFD166;font:40px sans-serif;display:grid;place-items:center;height:300px'>渲染 OK</body>");
await new Promise(r => setTimeout(r, 200));
await p.screenshot({ path: process.argv[2] });
await b.close();
console.log("OK " + exe);
''')
    png = os.path.join(TMP, "shot.png")
    r = subprocess.run(["node", probe, png], capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(png):
        ok((r.stdout.strip() or "")[:70])
        ok("截图 %d 字节" % os.path.getsize(png))
    elif "NO_BROWSER" in r.stdout:
        bad("找不到 Chrome / Edge", "装一个，或改 capture.mjs 里的 CHROME 常量")
    else:
        bad((r.stderr or r.stdout).strip()[:160],
            "设 NODE_PATH=<node_modules 路径>，或 npm i puppeteer-core")
except Exception as e:
    bad(repr(e))

# ---------- 结论 ----------
print("\n" + "=" * 58)
if FAIL:
    print("有 %d 项没通过 —— 上面每条都写了怎么修。" % FAIL)
    print("四项全通过之前，生产管线跑不通。")
    sys.exit(1)
else:
    print("四项全通过。这台机器可以直接跑生产管线了。")
    print("下一步：读《交接文档.md》第 3 节「现在卡在哪」。")
