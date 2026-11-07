# -*- coding: utf-8 -*-
"""render_all.py — 6 期串行渲染 + 混流 + 归档（2026-11-01 批）

为什么要串行：capture.mjs 的 worker 固定监听 8130 端口，两期同时跑会 EADDRINUSE，
而失败时 mux 仍会用旧帧合出一个「看着成功」的 mp4（NO.22 踩过）。

用法：
    python "02 工具/render_all.py"                 # 全 6 期
    python "02 工具/render_all.py" NO.19           # 只跑一期
    python "02 工具/render_all.py" --mux-only      # 只混流（画面已渲好）

每期产物：
    30 制作/<期>/web/render.mp4          无声画面
    30 制作/<期>/web/final.mp4           成片
    30 制作/<期>/30_交付/...             成片 + 封面 ×3 + 标题与描述
    40 出版物/<日期>/<期号>/              同上（发布归档）
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = os.path.join(ROOT, "30 制作")
PUB = os.path.join(ROOT, "40 出版物")
LOG = os.path.join(ROOT, "02 工具", "_render_log")
NODE_PATH = "C:/Users/13071/.workbuddy/binaries/node/workspace/node_modules"
PY = sys.executable

# 期号 -> (期目录名, 发布日)
EPS = [
    ("NO.18", "2026-11-02_围一圈报数", "2026-11-02"),
    ("NO.19", "2026-11-03_地球加长一米", "2026-11-03"),
    ("NO.20", "2026-11-04_住满的旅馆", "2026-11-04"),
    ("NO.21", "2026-11-05_两扇门", "2026-11-05"),
    ("NO.22", "2026-11-06_少了一格", "2026-11-06"),
    ("NO.23", "2026-11-07_蒙眼分硬币", "2026-11-07"),
]
SEG = 128
PORT = 8130


def log(msg, fh=None):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


def run(cmd, cwd, env=None, timeout=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       env=env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def render_one(no, ep, fh):
    """串行渲染一期：分段 → 拼片 → 校验帧数"""
    web = os.path.join(PROD, ep, "web")
    tl_p = os.path.join(web, "timeline.json")
    if not os.path.exists(tl_p):
        log("  ✗ 缺 timeline.json", fh); return False
    tl = json.load(open(tl_p, encoding="utf-8"))
    frames = round(tl["duration"] * 30)
    nseg = (frames + SEG - 1) // SEG
    log("  时长 %.2fs / %d 帧 / %d 段" % (tl["duration"], frames, nseg), fh)

    env = dict(os.environ, NODE_PATH=NODE_PATH)
    segdir = os.path.join(web, "_seg")
    os.makedirs(segdir, exist_ok=True)

    for i in range(nseg):
        s, e = i * SEG, min(i * SEG + SEG - 1, frames - 1)
        out = "s%d.mp4" % i
        outp = os.path.join(segdir, out)
        # 断点续跑：已有且大小合理就跳过
        if os.path.exists(outp) and os.path.getsize(outp) > 20000:
            log("  [%d/%d] 已存在，跳过" % (i + 1, nseg), fh)
            continue
        for attempt in (1, 2):
            rc, out_txt = run(["node", "capture.mjs", "--worker",
                               "--start", str(s), "--end", str(e),
                               "--port", str(PORT), "--out", "_seg/" + out],
                              cwd=web, env=env, timeout=900)
            if rc == 0 and os.path.exists(outp) and os.path.getsize(outp) > 20000:
                log("  [%d/%d] %d-%d ok" % (i + 1, nseg, s, e), fh)
                break
            log("  [%d/%d] 第 %d 次失败：%s" % (i + 1, nseg, attempt, out_txt[-300:]), fh)
        else:
            log("  ✗ 段 %d 反复失败，中止本期" % i, fh); return False

    # 拼片（_seg 内用相对名：绝对 UNC 路径会拼出 _seg/_seg/...）
    lst = os.path.join(segdir, "list.txt")
    open(lst, "w", encoding="utf-8").write(
        "\n".join("file 's%d.mp4'" % i for i in range(nseg)))
    rc, out = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", "list.txt", "-c", "copy", "../render.mp4"], cwd=segdir)
    if rc != 0:
        log("  ✗ 拼片失败：%s" % out[-300:], fh); return False
    rc, n = run(["ffprobe", "-v", "error", "-select_streams", "v",
                 "-show_entries", "stream=nb_frames", "-of", "default=nw=1:nk=1",
                 "render.mp4"], cwd=web)
    n = n.strip()
    if n != str(frames):
        log("  ✗ 帧数不符：%s / %d" % (n, frames), fh); return False
    log("  ✓ render.mp4 %s 帧" % n, fh)
    return True


def collect_sfx(ep, fh):
    """worker 模式不收集音效，单独跑一次 __collectSFX 写 sfx.json"""
    web = os.path.join(PROD, ep, "web")
    js = r"""
const puppeteer=require('puppeteer-core');const path=require('path');const fs=require('fs');
(async()=>{const b=await puppeteer.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',
 headless:'shell',args:['--headless=new','--no-sandbox','--disable-gpu']});
const p=await b.newPage();await p.setViewport({width:1080,height:1440});
await p.goto('file:///'+path.resolve('index.html').replace(/\\/g,'/')+'?capture=1',{waitUntil:'load'});
await p.waitForFunction('window.__ready===true',{timeout:30000});
const list=await p.evaluate('window.__collectSFX()');
fs.writeFileSync('sfx.json',JSON.stringify(list,null,1));
console.log('sfx '+list.length);
await b.close();})();
"""
    env = dict(os.environ, NODE_PATH=NODE_PATH)
    rc, out = run(["node", "-e", js], cwd=web, env=env, timeout=180)
    log("  sfx: %s" % out.strip().replace("\n", " "), fh)
    return rc == 0


def voice_one(ep, fh):
    """用 audio/ 里的配音重建 web/voice.wav。**混流之前必须跑**，
    否则 mux 用的是上一版留下的音轨（画面新、声音旧，且不报错）。"""
    web = os.path.join(PROD, ep, "web")
    env = dict(os.environ, PATH="C:/Users/13071/AppData/Local/Microsoft/WinGet/Packages/"
               "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin;"
               + os.environ.get("PATH", ""))
    rc, out = run([PY, "build_voice.py"], cwd=web, env=env, timeout=600)
    if rc != 0:
        log("  ✗ build_voice 失败：%s" % out[-300:], fh); return False
    log("  voice: " + out.strip().splitlines()[-1], fh)
    return True


def mux_one(ep, fh):
    web = os.path.join(PROD, ep, "web")
    env = dict(os.environ, PATH="C:/Users/13071/bin;" + os.environ.get("PATH", ""))
    rc, out = run([PY, "mux.py", "final.mp4"], cwd=web, env=env, timeout=1800)
    tail = "\n".join([ln for ln in out.strip().split("\n") if ln.strip()][-6:])
    log("  mux:\n" + tail, fh)
    return rc == 0 and os.path.exists(os.path.join(web, "final.mp4"))


def cover_one(no, ep, outdir, fh):
    """生成 5 版封面，挑 G 版（标题党大字报）改名，其余进候选归档"""
    env = dict(os.environ, PATH="C:/Users/13071/bin/;" + os.environ.get("PATH", ""))
    rc, out = run([PY, os.path.join(ROOT, "02 工具", "_covers.py"), ep, "--out", outdir],
                  cwd=ROOT, env=env, timeout=600)
    # ★ _covers.py 返回 2 = 「图都出来了，但版面体检有警告」（文案偏长之类）。
    #   以前一律当失败，结果改名那一步被跳过，交付里留的是上一版旧封面。
    if rc not in (0, 2):
        log("  ✗ 封面生成失败：%s" % out[-400:], fh); return False
    if rc == 2:
        log("  ! 封面有版面警告（照常出图，见 _covers 输出）", fh)
    # 找 G 版三种比例
    cand = [f for f in os.listdir(outdir) if f.startswith("封面G_")]
    if not cand:
        log("  ✗ 没找到 G 版封面：%s" % os.listdir(outdir)[:6], fh); return False
    n = no.replace(".", "")
    # ★ 封面文件名的标题要取 covers.json 的 title，不是目录名。
    #   用目录名的话，改过标题的封面会在每次渲染时被冲回旧名字（NO.20 踩过三次）。
    title = ep.split("_", 1)[1]
    try:
        cj = os.path.join(ROOT, "30 制作", ep, "covers.json")
        if os.path.exists(cj):
            title = json.load(open(cj, encoding="utf-8")).get("title") or title
    except Exception:
        pass
    pick = {}
    for f in cand:
        if f.endswith("_横版.png"):
            pick[f] = "封面_%s_%s_横版.png" % (no, title)
        elif f.endswith("_16x9.png"):
            pick[f] = "封面_%s_%s_16x9.png" % (no, title)
        else:
            pick[f] = "封面_%s_%s.png" % (no, title)
    box = os.path.join(ROOT, "99 归档", "_封面候选_%s" % n)
    os.makedirs(box, exist_ok=True)
    for f in os.listdir(outdir):
        if not f.startswith("封面"):
            continue
        src = os.path.join(outdir, f)
        if f in pick:
            dst = os.path.join(outdir, pick[f])
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)
        else:
            try:
                shutil.move(src, os.path.join(box, f))
            except Exception:
                pass
    log("  封面: " + ", ".join(sorted(pick.values())), fh)
    return True


def deliver(no, ep, date, fh):
    """成片 + 封面 + 标题描述 归到 30_交付/ 和 40 出版物/<日期>/<期号>/"""
    web = os.path.join(PROD, ep, "web")
    src = os.path.join(web, "final.mp4")
    if not os.path.exists(src):
        log("  ✗ 没有 final.mp4", fh); return False
    # 画幅决定文件名：1920×1080 → 横屏，1080×1440 → 竖屏（2026-11-03 起 16:9 是主线）
    try:
        _sz = json.load(open(os.path.join(web, "size.json"), encoding="utf-8"))
        _ori = "横屏" if int(_sz["width"]) > int(_sz["height"]) else "竖屏"
    except Exception:
        _ori = "竖屏"
    want = "%s_%s_%s.mp4" % (no, ep.split("_", 1)[1], _ori)
    dirs = [os.path.join(PROD, ep, "30_交付"), os.path.join(PUB, date, ep)]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        shutil.copy(src, os.path.join(d, want))
    log("  成片 -> %s" % " | ".join(dirs), fh)
    # 封面
    for d in dirs:
        cover_one(no, ep, d, fh)
    # 标题与描述
    txt_src = os.path.join(PROD, ep, "30_交付", "标题与描述_%s_%s.txt" % (no, ep.split("_", 1)[1]))
    if os.path.exists(txt_src):
        shutil.copy(txt_src, os.path.join(PUB, date, ep, os.path.basename(txt_src)))
    return True


def main():
    os.makedirs(LOG, exist_ok=True)
    args = sys.argv[1:]
    only = [a for a in args if a.startswith("NO.")]
    mux_only = "--mux-only" in args
    todo = [e for e in EPS if (not only or e[0] in only)]

    for no, ep, date in todo:
        fh = open(os.path.join(LOG, "%s.log" % no.replace(".", "")), "w", encoding="utf-8")
        log("\n========== %s %s ==========" % (no, ep), fh)
        ok = True
        if not mux_only:
            ok = render_one(no, ep, fh)
        if ok:
            collect_sfx(ep, fh)
            if not voice_one(ep, fh):
                log("  ✗ 跳过混流（音轨没建好）", fh); continue
            ok = mux_one(ep, fh)
        if ok:
            ok = deliver(no, ep, date, fh)
        log("  === %s %s ===\n" % (no, "完成" if ok else "失败"), fh)
        fh.close()
        if not ok:
            print("!! %s 失败，日志见 02 工具/_render_log/%s.log" % (no, no.replace(".", "")))
            sys.exit(1)


if __name__ == "__main__":
    main()
