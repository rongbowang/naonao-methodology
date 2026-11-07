# -*- coding: utf-8 -*-
"""render_all.py — 渲染 + 混流 + 交付

## 2026-11-07 改版说明

1. **期清单不再硬编码**。原来 `EPS` 只写到 NO.23，传 `NO.24` 会静默得到空列表、
   什么也不跑还 exit 0 —— 这个坑已修：现在扫 `30 制作/*/script.py` 动态读 `NO`，
   且 `NO.xx` 匹配不到时**报错退出（exit 2）**并列出可用期号。
2. **分段可并发**。原来逐段串行（128 帧一段，一段一跑），全片 130 分钟。
   现在 `--par=N` 并发 N 段，端口从 `--port`（默认 8130）起按槽位分配，
   每槽独占一个端口，不会 EADDRINUSE。**默认 par=1，行为与旧版一致。**
3. **单镜试渲**。`--pilot=00_open` 只渲这一镜到 `web/pilot_00_open.mp4`，
   不碰 `render.mp4`、不 concat 全片。用途：20 分钟内看到真实成片的构图/字幕/
   安全区/节奏，再决定是否全片渲染（全片 130 分钟，返工太贵）。
4. 多期同时跑仍然要串行 —— 但理由变了：不是"8130 被占死"，而是**端口段会重叠**。
   两期并行时给不同基址：`--port=8140` / `--port=8150`（每期占 base..base+par-1）。

用法：
    python "02 工具/render_all.py"                      # 跑全部已立项的期
    python "02 工具/render_all.py" NO.29                # 只跑一期
    python "02 工具/render_all.py" NO.29 --par=4        # 分段并发 4 路
    python "02 工具/render_all.py" NO.29 --pilot=00_open  # 只试渲开场镜
    python "02 工具/render_all.py" NO.29 --mux-only     # 只混流（画面已渲好）

每期产物：
    30 制作/<期>/web/render.mp4          无声画面
    30 制作/<期>/web/final.mp4           成片
    30 制作/<期>/30_交付/...             成片 + 封面 ×3 + 标题与描述
    40 出版物/<日期>/<期号>/              同上（发布归档）
"""
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = os.path.join(ROOT, "30 制作")
PUB = os.path.join(ROOT, "40 出版物")
LOG = os.path.join(ROOT, "02 工具", "_render_log")
NODE_PATH = "C:/Users/13071/.workbuddy/binaries/node/workspace/node_modules"
PY = sys.executable

SEG = 128
PORT = 8130
_LOG_LOCK = threading.Lock()


def discover_eps():
    """扫 30 制作/ 下的期目录，从 script.py 读 NO。返回 [(no, 目录名, 日期)]。

    只认同时具备 script.py 与 web/timeline.json 的目录 —— 没有 timeline 的
    是还没走到渲染的期，不该出现在渲染清单里。
    """
    out = []
    if not os.path.isdir(PROD):
        return out
    for d in sorted(os.listdir(PROD)):
        ep_dir = os.path.join(PROD, d)
        sp = os.path.join(ep_dir, "script.py")
        if not os.path.isdir(ep_dir) or not os.path.exists(sp):
            continue
        try:
            src = open(sp, encoding="utf-8").read()
        except Exception:
            continue
        m = re.search(r'^NO\s*=\s*["\'](NO\.\d+)["\']', src, re.M)
        if not m:
            continue
        out.append((m.group(1), d, d[:10]))
    return out


def log(msg, fh=None):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    with _LOG_LOCK:
        print(line, flush=True)
        if fh:
            fh.write(line + "\n")
            fh.flush()


def run(cmd, cwd, env=None, timeout=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       env=env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _render_seg(web, env, segdir, i, s, e, port, fh, out_name):
    """渲一段。已有且大小合理就跳过（断点续跑）。返回 (序号, 成功?)"""
    outp = os.path.join(segdir, out_name)
    if os.path.exists(outp) and os.path.getsize(outp) > 20000:
        log("  [段%d] 已存在，跳过" % (i + 1), fh)
        return (i, True)
    for attempt in (1, 2):
        rc, out_txt = run(["node", "capture.mjs", "--worker",
                           "--start", str(s), "--end", str(e),
                           "--port", str(port), "--out", "_seg/" + out_name],
                          cwd=web, env=env, timeout=900)
        if rc == 0 and os.path.exists(outp) and os.path.getsize(outp) > 20000:
            log("  [段%d] %d-%d ok（端口 %d）" % (i + 1, s, e, port), fh)
            return (i, True)
        log("  [段%d] 第 %d 次失败：%s" % (i + 1, attempt, out_txt[-300:]), fh)
    return (i, False)


def _seg_range(i, frames, seg=SEG):
    return i * seg, min(i * seg + seg - 1, frames - 1)


def _run_segs(web, env, segdir, nseg, frames, par, base_port, fh, prefix="s"):
    """并发跑 nseg 段，每个槽位独占一个端口（不会 EADDRINUSE）。"""
    par = max(1, par)
    port_pool = queue.Queue()
    for k in range(par):
        port_pool.put(base_port + k)

    def task(i):
        s, e = _seg_range(i, frames)
        port = port_pool.get()
        try:
            return _render_seg(web, env, segdir, i, s, e, port, fh, "%s%d.mp4" % (prefix, i))
        finally:
            port_pool.put(port)

    with ThreadPoolExecutor(max_workers=par) as ex:
        results = list(ex.map(task, range(nseg)))
    bad = [r[0] for r in results if not r[1]]
    if bad:
        log("  ✗ 段 %s 失败，中止" % ", ".join(str(x + 1) for x in bad), fh)
        return False
    return True


def _concat(segdir, nseg, out_rel, fh, prefix="s"):
    lst = os.path.join(segdir, "list.txt")
    open(lst, "w", encoding="utf-8").write(
        "\n".join("file '%s%d.mp4'" % (prefix, i) for i in range(nseg)))
    rc, out = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", "list.txt", "-c", "copy", out_rel], cwd=segdir)
    if rc != 0:
        log("  ✗ 拼片失败：%s" % out[-300:], fh)
        return False
    return True


def _port_free(port):
    """试 bind 127.0.0.1:port，能绑=空闲。任何异常都算被占（宁误报不静默）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def render_one(no, ep, fh, par=1, base_port=PORT):
    """渲染一期：分段（可并发）→ 拼片 → 校验帧数"""
    web = os.path.join(PROD, ep, "web")
    tl_p = os.path.join(web, "timeline.json")
    if not os.path.exists(tl_p):
        log("  ✗ 缺 timeline.json", fh); return False
    tl = json.load(open(tl_p, encoding="utf-8"))
    frames = round(tl["duration"] * 30)
    nseg = (frames + SEG - 1) // SEG
    log("  时长 %.2fs / %d 帧 / %d 段 / 并发 %d" % (tl["duration"], frames, nseg, par), fh)

    env = dict(os.environ, NODE_PATH=NODE_PATH)
    segdir = os.path.join(web, "_seg")
    os.makedirs(segdir, exist_ok=True)

    if not _run_segs(web, env, segdir, nseg, frames, par, base_port, fh):
        return False

    if not _concat(segdir, nseg, "../render.mp4", fh):
        return False
    rc, n = run(["ffprobe", "-v", "error", "-select_streams", "v",
                 "-show_entries", "stream=nb_frames", "-of", "default=nw=1:nk=1",
                 "render.mp4"], cwd=web)
    n = n.strip()
    if n != str(frames):
        log("  ✗ 帧数不符：%s / %d" % (n, frames), fh); return False
    log("  ✓ render.mp4 %s 帧" % n, fh)
    return True


def render_pilot(no, ep, shot_id, fh, par=1, base_port=PORT):
    """只渲一镜到 web/pilot_<shot>.mp4，不碰 render.mp4。

    用途：20 分钟内看到真实成片（字幕位置/安全区/构图/节奏），再决定要不要全片。
    """
    web = os.path.join(PROD, ep, "web")
    tl_p = os.path.join(web, "timeline.json")
    if not os.path.exists(tl_p):
        log("  ✗ 缺 timeline.json", fh); return False
    tl = json.load(open(tl_p, encoding="utf-8"))
    shots = tl.get("shots", [])
    s = next((x for x in shots if x.get("id") == shot_id), None)
    if s is None:
        log("  ✗ 没有这一镜：%s" % shot_id, fh)
        log("    可用镜号：%s" % ", ".join(x.get("id", "?") for x in shots), fh)
        return False

    fps = tl.get("fps", 30)
    f0 = int(round(s["start"] * fps))
    f1 = int(round(s["end"] * fps))
    frames = f1 - f0 + 1
    nseg = (frames + SEG - 1) // SEG
    log("  试渲 %s：%.2f~%.2fs / %d 帧 / %d 段 / 并发 %d"
        % (shot_id, s["start"], s["end"], frames, nseg, par), fh)

    env = dict(os.environ, NODE_PATH=NODE_PATH)
    segdir = os.path.join(web, "_pilot")
    if os.path.isdir(segdir):
        shutil.rmtree(segdir, ignore_errors=True)
    os.makedirs(segdir, exist_ok=True)

    par = max(1, par)
    port_pool = queue.Queue()
    for k in range(par):
        port_pool.put(base_port + k)

    def task(i):
        s0, e0 = i * SEG, min(i * SEG + SEG - 1, frames - 1)
        port = port_pool.get()
        try:
            out = "p%d.mp4" % i
            rc, _ = run(["node", "capture.mjs", "--worker",
                         "--start", str(f0 + s0), "--end", str(f0 + e0),
                         "--port", str(port), "--out", "_pilot/" + out],
                        cwd=web, env=env, timeout=900)
            return (i, rc == 0 and os.path.exists(os.path.join(segdir, out)))
        finally:
            port_pool.put(port)

    with ThreadPoolExecutor(max_workers=par) as ex:
        results = list(ex.map(task, range(nseg)))
    if not all(r[1] for r in results):
        log("  ✗ 试渲有段失败", fh); return False

    out_mp4 = "pilot_%s.mp4" % shot_id
    lst = os.path.join(segdir, "list.txt")
    open(lst, "w", encoding="utf-8").write(
        "\n".join("file 'p%d.mp4'" % i for i in range(nseg)))
    rc, out = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", "list.txt", "-c", "copy", "../" + out_mp4], cwd=segdir)
    if rc != 0:
        log("  ✗ 拼片失败：%s" % out[-300:], fh); return False

    rc, n = run(["ffprobe", "-v", "error", "-select_streams", "v",
                 "-show_entries", "stream=nb_frames", "-of", "default=nw=1:nk=1",
                 out_mp4], cwd=web)
    if n.strip() != str(frames):
        log("  ✗ 帧数不符：%s / %d" % (n.strip(), frames), fh); return False
    log("  ✓ %s（%s 帧）→ 先看它，再决定要不要全片渲染" % (out_mp4, n.strip()), fh)
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


LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".render.lock")
MAX_WAIT = 24 * 3600         # 排在后面最多等 24 小时（一期全片 ~130 分钟，够排 10 期）
MAX_LOCK_AGE = 8 * 3600      # 锁文件超过 8 小时基本是死锁（防 pid 复用误判）


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


_HB = {"stop": None}


def _start_heartbeat():
    """持锁期间每 3 秒刷一次锁文件 mtime。等锁方靠它判断"持有者还活着"，
    不再依赖 pid 活性 —— Windows 上 pid 复用很快，靠 pid 会误判成活锁而永久排队。"""
    ev = threading.Event()

    def loop():
        while not ev.wait(3):
            try:
                os.utime(LOCK, None)
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True).start()
    _HB["stop"] = ev


def _stop_heartbeat():
    ev = _HB.get("stop")
    if ev:
        ev.set()
        _HB["stop"] = None


def acquire_render_lock(tag):
    """全局渲染互斥锁：同一时刻只允许一个 render_all 进程在渲。

    为什么要有它：capture.mjs 撞端口时 **不报错**，还会合出一个能播的空 mp4。
    `--port` 分段是约定，人一忘就破；这把锁是机制，破不了。

    锁文件内容：`<pid> <期号>`。上一轮崩了留下死锁时，靠 pid 活性 + 锁龄兜底自动接管。

    实现要点：**必须用 O_CREAT|O_EXCL 原子创建**。
    曾经写成"先 os.path.exists 判断、再 open 写入"，压力测试里 8 个进程同时抢，
    8 个全部"抢到"、28 对持锁区间全重叠 —— 判存在和写文件之间没有原子性，
    这是个假锁。CREATE_NEW 由内核保证只有一个能建成。
    """
    me = os.getpid()
    waited = 0
    last_note = -60
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            other, who, age = -1, "?", 0.0
            try:
                raw = open(LOCK, "r", encoding="utf-8").read().split()
                other = int(raw[0]) if raw else -1
                who = raw[1] if len(raw) > 1 else "?"
                age = time.time() - os.path.getmtime(LOCK)
            except Exception:
                pass
            # 死锁判定：60 秒没心跳 = 持有者没了（心跳 3 秒一次，容忍 20 次抖动）
            # 辅以 pid 活性做快速判定；不以 pid 为主，因为 Windows 会很快复用 pid
            stale = age > 60 or (other > 0 and not _pid_alive(other))
            if stale:
                print("   接管残留渲染锁（pid %d / 锁龄 %.0fs，上一轮没正常退出）" % (other, age))
                try:
                    os.remove(LOCK)
                except Exception:
                    pass
                continue
            if waited - last_note >= 60:
                print("   另一路渲染正在跑（%s / pid %d），已等 %d 秒，继续排队…"
                      % (who, other, waited))
                last_note = waited
            time.sleep(1)
            waited += 1
            if waited > MAX_WAIT:
                print("!! 等渲染锁超过 %d 小时，放弃（先确认另一路是不是卡死了）" % (MAX_WAIT // 3600))
                return False
            continue
        except OSError as e:
            print("!! 拿渲染锁出错：%s" % e)
            return False
        # 建成即持有；写入自己的身份，并开始心跳
        try:
            os.write(fd, ("%d %s" % (me, tag)).encode("utf-8"))
        finally:
            os.close(fd)
        _start_heartbeat()
        return True


def release_render_lock():
    _stop_heartbeat()
    try:
        if os.path.exists(LOCK):
            raw = open(LOCK, "r", encoding="utf-8").read().split()
            if raw and int(raw[0]) == os.getpid():
                os.remove(LOCK)
    except Exception:
        pass


def main():
    os.makedirs(LOG, exist_ok=True)
    args = sys.argv[1:]
    only = [a for a in args if a.startswith("NO.")]
    mux_only = "--mux-only" in args
    par = int(next((a.split("=", 1)[1] for a in args if a.startswith("--par=")), "1"))
    base_port = int(next((a.split("=", 1)[1] for a in args if a.startswith("--port=")), str(PORT)))
    pilot = next((a.split("=", 1)[1] for a in args if a.startswith("--pilot=")), None)
    no_lock = "--no-lock" in args

    all_eps = discover_eps()
    if not all_eps:
        print('!! 30 制作 下没有可渲染的期（要求 script.py 里有 NO = "NO.xx"）')
        sys.exit(2)
    todo = [e for e in all_eps if (not only or e[0] in only)]
    if only and not todo:
        print("!! 没有匹配的期：%s" % ", ".join(only))
        print("   30 制作 下现有的：%s" % ", ".join(e[0] for e in all_eps))
        sys.exit(2)

    # ---- 全局渲染锁：不管谁、怎么调，同一时刻只有一路在渲 ----
    if not no_lock:
        if not acquire_render_lock(" ".join(only) if only else "ALL"):
            sys.exit(3)
    else:
        print("!! --no-lock：跳过渲染锁，两路同时渲会撞端口且静默产出空 mp4，出事自己负责")

    # ---- 端口自检：capture.mjs 撞端口 **不报错**，会静默合出"能播的空 mp4"。
    #      槽位分配与 _run_segs 同一套：base_port + 0 .. base_port + par - 1。
    #      --mux-only 不渲画面，不占槽位，不检。 ----
    if not mux_only:
        busy = [p for p in range(base_port, base_port + max(1, par)) if not _port_free(p)]
        if busy:
            print("!! 端口 %s 被占用（多半是上次渲染被强杀的孤儿 node），先清进程再渲" %
                  "、".join(str(p) for p in busy))
            sys.exit(4)

    try:
        for no, ep, date in todo:
            fh = open(os.path.join(LOG, "%s.log" % no.replace(".", "")), "w", encoding="utf-8")
            log("\n========== %s %s ==========" % (no, ep), fh)

            if pilot:
                ok = render_pilot(no, ep, pilot, fh, par=par, base_port=base_port)
                log("  === %s 试渲%s ===\n" % (no, "完成" if ok else "失败"), fh)
                fh.close()
                if not ok:
                    sys.exit(1)
                continue

            ok = True
            if not mux_only:
                ok = render_one(no, ep, fh, par=par, base_port=base_port)
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
    finally:
        release_render_lock()


if __name__ == "__main__":
    main()
