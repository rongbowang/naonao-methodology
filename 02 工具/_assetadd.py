#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""_assetadd.py — 素材入库（带文件锁，多窗口并发安全）

为什么要它：graphics_catalog.json / sfx_catalog.json 各是一个文件、多期共用。
九个窗口同时「读-改-写」会互相覆盖，最后只剩最后一期的条目。
本脚本用 O_CREAT|O_EXCL 锁文件把追加操作串行化，并做幂等（同名/同 id 不重复追加）。

用法：
  # 查库（不用锁，只读）
  python _assetadd.py find --q coin [--kind gfx|sfx] [--limit 20]

  # 图形入库：--svg-file 指向一个完整 .svg（脚本自动抽 <path d="...">）
  python _assetadd.py gfx --name "硬币" --group "钱数据" --tags "coin,money" --svg-file "D:\...\coin.svg"

  # 音效入库
  python _assetadd.py sfx --id "coin-flip" --file "D:\...\coin-flip.wav" --category "money" --sync-at 0.01

  # 只登记、不拷文件（素材文件已经手工放好了）
  python _assetadd.py gfx --name "硬币" --group "钱数据" --tags "coin,money" --body-file "D:\...\d.txt"
退出码：0 成功（含幂等命中） / 1 参数或数据错误 / 3 等锁超时
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAT = ROOT / "20 素材_只读"
GFX_CAT = MAT / "graphics_catalog.json"
SFX_CAT = MAT / "sfx_catalog.json"
GFX_DIR = MAT / "graphics"
SFX_DIR = MAT / "sfx"
LOCK = HERE / ".asset.lock"
GROUPS = ["水", "动物", "工具仪器", "书纸笔", "建筑", "植物自然",
          "钱数据", "医疗", "人物姿态", "天体", "人体"]
MAX_WAIT = 900          # 等锁上限 15 分钟：九路并发，单条写入只有几十毫秒，足够
ID_MAX = None           # 由 gfx 逻辑按现有最大值 +1 分配


def out(msg): print(msg)


def _pid_alive(pid: int) -> bool:
    """Windows 上绝不能用 os.kill(pid, 0) 探活 —— CPython 在 Windows 的 os.kill
    对 sig!=CTRL_* 一律走 TerminateProcess(h, sig)，等于直接把对方进程杀掉。
    实测后果：等待者读锁里的 pid → 杀掉持锁者 → 锁变残留 → 下一个人再杀下一个 → 全体卡死。
    必须改用 OpenProcess + GetExitCodeProcess 查询。"""
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == 259                 # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


# ---------------- 锁 ----------------

class Lock:
    def __init__(self, path: Path, max_wait: int = MAX_WAIT):
        self.path, self.max_wait, self.fd = path, max_wait, None

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                # 残留锁：超过 60 秒且写入者已不在，接管
                try:
                    age = time.time() - self.path.stat().st_mtime
                    pid = int(self.path.read_text(encoding="utf-8").strip() or 0)
                except Exception:
                    age, pid = 0, 0
                alive = _pid_alive(pid)
                if age > 60 and not alive:
                    try:
                        self.path.unlink()
                        out("  （接管残留锁，pid %d 已不在）" % pid)
                    except OSError:
                        pass
                    continue
                if time.time() - t0 > self.max_wait:
                    raise TimeoutError("等素材锁超时（%d 秒），另一个窗口可能卡死了" % self.max_wait)
                time.sleep(0.5)

    def __exit__(self, *a):
        try:
            if self.fd is not None:
                os.close(self.fd)
        finally:
            try:
                self.path.unlink()
            except OSError:
                pass


# ---------------- 读写 ----------------

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data):
    """先写 .tmp 再 os.replace，保证读的人永远看到完整 JSON。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(path))


def backup_once(path: Path):
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(str(path), str(bak))
        out("  首次改动，已备份 %s" % bak.name)


# ---------------- 查库 ----------------

def cmd_find(args):
    q = args["q"].lower()
    kind = args.get("kind", "both")
    limit = int(args.get("limit", 20))
    n = 0
    if kind in ("gfx", "both"):
        d = load(GFX_CAT)
        for x in d["items"]:
            hay = (str(x.get("name", "")) + " " + str(x.get("tags", "")) + " " + str(x.get("group", ""))).lower()
            if q in hay:
                out("GFX  %-6s %-10s %-32s | %s" % (x.get("id"), x.get("group"), x.get("name"), x.get("tags")))
                n += 1
                if n >= limit:
                    break
    if kind in ("sfx", "both") and n < limit:
        d = load(SFX_CAT)
        for x in d["sounds"]:
            hay = (str(x.get("id", "")) + " " + str(x.get("category", "")) + " " + " ".join(x.get("tags", []))).lower()
            if q in hay:
                out("SFX  %-38s %-22s %.2fs" % (x.get("id"), x.get("category"), x.get("duration", 0)))
                n += 1
                if n >= limit:
                    break
    if n == 0:
        out("（库里没有命中「%s」）" % args["q"])
    out("共 %d 条" % n)
    return 0


# ---------------- 图形入库 ----------------

def _extract_path_d(svg_text: str) -> str:
    ds = re.findall(r'<path[^>]*\sd="([^"]+)"', svg_text, re.S)
    if not ds:
        raise ValueError("svg 里找不到 <path d=\"...\">")
    return " ".join(ds)


def _extract_viewbox(svg_text: str) -> str:
    m = re.search(r'viewBox="([^"]+)"', svg_text)
    return m.group(1) if m else ""


def cmd_gfx(args):
    name = args["name"].strip()
    group = args["group"].strip()
    tags = args.get("tags", "").strip()
    if group not in GROUPS:
        out("!! group 必须是这 11 类之一：%s" % " / ".join(GROUPS))
        return 1

    svg_file = args.get("svg-file")
    body_file = args.get("body-file")
    if svg_file:
        txt = io.open(svg_file, encoding="utf-8", errors="ignore").read()
        body = _extract_path_d(txt)
        viewbox = args.get("viewbox") or _extract_viewbox(txt)
        dest = GFX_DIR / (Path(svg_file).stem + ".svg")
    elif body_file:
        body = io.open(body_file, encoding="utf-8", errors="ignore").read().strip()
        viewbox = args.get("viewbox", "")
        dest = None
    else:
        out("!! 需要 --svg-file 或 --body-file")
        return 1

    with Lock(LOCK):
        d = load(GFX_CAT)
        for x in d["items"]:
            if str(x.get("name", "")).strip() == name:
                out("  = 已存在，跳过（幂等）：id=%s %s" % (x.get("id"), name))
                return 0
        if dest is not None:
            GFX_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(svg_file, str(dest))
        ids = [x["id"] for x in d["items"] if isinstance(x.get("id"), int)]
        new_id = (max(ids) + 1) if ids else 1
        d["items"].append({
            "id": new_id, "name": name, "group": group,
            "tags": tags, "viewBox": viewbox, "body": body,
        })
        d["count"] = len(d["items"])
        backup_once(GFX_CAT)
        save(GFX_CAT, d)
        out("  + 图形入库 id=%d  %s / %s  共 %d 条%s" % (
            new_id, name, group, d["count"], ("  文件→" + str(dest.name)) if dest else ""))
    return 0


# ---------------- 音效入库 ----------------

def cmd_sfx(args):
    sid = args["id"].strip()
    src = args.get("file")
    category = args.get("category", "misc")
    with Lock(LOCK):
        d = load(SFX_CAT)
        for x in d["sounds"]:
            if x.get("id") == sid:
                out("  = 已存在，跳过（幂等）：%s" % sid)
                return 0
        if src:
            if not Path(src).exists():
                out("!! 文件不存在：%s" % src)
                return 1
            SFX_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, str(SFX_DIR / (sid + ".wav")))
        d["sounds"].append({
            "id": sid, "name": args.get("name", sid), "category": category,
            "duration": float(args.get("duration", 0)), "channels": 1,
            "sync_at": float(args.get("sync-at", 0)), "sync_meets": args.get("sync-meets", ""),
            "lufs": None, "true_peak_dbtp": None, "under_voiceover_db": -3,
            "fits_seconds": [], "tags": [t for t in args.get("tags", "").split(",") if t],
            "use_for": [],
        })
        d["count"] = len(d["sounds"])
        backup_once(SFX_CAT)
        save(SFX_CAT, d)
        out("  + 音效入库 %s / %s  共 %d 条%s" % (sid, category, d["count"],
                                                 ("  文件→%s.wav" % sid) if src else "（仅登记，无文件）"))
    return 0


# ---------------- main ----------------

def parse(argv):
    if not argv:
        out(__doc__)
        return None, None
    cmd, rest = argv[0], argv[1:]
    kv = {}
    i = 0
    while i < len(rest):
        a = rest[i]
        if a.startswith("--"):
            k = a[2:]
            if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                kv[k] = rest[i + 1]
                i += 2
            else:
                kv[k] = "1"
                i += 1
        else:
            i += 1
    return cmd, kv


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd, kv = parse(sys.argv[1:])
    if cmd is None:
        return 1
    try:
        if cmd == "find":
            return cmd_find(kv)
        if cmd == "gfx":
            return cmd_gfx(kv)
        if cmd == "sfx":
            return cmd_sfx(kv)
        out("!! 未知子命令：%s（可用：find / gfx / sfx）" % cmd)
        return 1
    except TimeoutError as e:
        out("!! %s" % e)
        return 3
    except Exception as e:
        out("!! %s: %s" % (type(e).__name__, e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
