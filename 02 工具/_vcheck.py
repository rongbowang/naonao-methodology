# -*- coding: utf-8 -*-
"""_vcheck.py — 配音新鲜度检查。

为什么要有这个：
    NO.22（2026-11-05）成片里是三天前的旧配音。原因是流水线里
    `tts_whole.py → gen_timeline.py → build_voice.py → mux.py` 这四步，
    我漏跑了 build_voice.py，于是 web/voice.wav 一直是老文件，
    mux 照常"成功"、成片照常出、所有体检都过 —— 但配的是上一期的台词。
    没有任何一步会报错，只能靠人耳听出来。

检查四件事：
    1. web/voice.wav 存在
    2. voice.wav 不比 audio/shots/ 里任何一段旧（更新过台词就必须重合成）
    3. voice.wav 的时长和 timeline.json 的 duration 对得上（差 < 1.5s）
    4. web/final.mp4 不比 voice.wav 旧（成片必须用当前这版音频混出来）

用法：
    python "02 工具/_vcheck.py" 2026-11-06_少了一格
    python "02 工具/_vcheck.py" 全         # 检查 30 制作/ 下所有期
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE = os.path.join(ROOT, "30 制作")
FFPROBE = "ffprobe"


def dur_of(path):
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:
        return None


def check_one(name):
    d = os.path.join(MAKE, name)
    web = os.path.join(d, "web")
    voice = os.path.join(web, "voice.wav")
    tl_p = os.path.join(web, "timeline.json")
    final = os.path.join(web, "final.mp4")
    shots = os.path.join(d, "audio", "shots")

    print("=" * 60)
    print(name)
    bad = []
    warn = []

    if not os.path.exists(voice):
        print("  [FAIL] 没有 web/voice.wav")
        return 1
    v_t = os.path.getmtime(voice)
    print("  voice.wav  %s  %.2f MB"
          % (iso(v_t), os.path.getsize(voice) / 1048576))

    # ① voice.wav 不能比任何一段分镜音频旧
    newest, newest_name = 0, ""
    if os.path.isdir(shots):
        for f in os.listdir(shots):
            if f.endswith(".wav"):
                t = os.path.getmtime(os.path.join(shots, f))
                if t > newest:
                    newest, newest_name = t, f
    if newest > v_t + 1:
        bad.append("voice.wav 比 audio/shots/%s 旧 %s —— 跑 web/build_voice.py"
                   % (newest_name, gap(v_t, newest)))
        print("  [FAIL] %s" % bad[-1])
    else:
        print("  [OK]   不比分镜音频旧（最新 %s %s）" % (newest_name, iso(newest)))

    # ② 时长要和 timeline 对得上
    if os.path.exists(tl_p):
        tl = json.load(open(tl_p, encoding="utf-8"))
        vd = dur_of(voice)
        exp = tl.get("duration", 0)
        if vd is None:
            bad.append("voice.wav 读不出时长")
            print("  [FAIL] %s" % bad[-1])
        else:
            diff = abs(vd - exp)
            if diff > 1.5:
                bad.append("voice.wav %.2fs，timeline 要 %.2fs，差 %.2fs"
                           % (vd, exp, diff))
                print("  [FAIL] %s" % bad[-1])
            else:
                print("  [OK]   时长 %.2fs（timeline %.2fs）" % (vd, exp))
    else:
        warn.append("没有 timeline.json，跳过时长核对")
        print("  [WARN] %s" % warn[-1])

    # ③ 成片必须是用这版音频混的
    if os.path.exists(final):
        f_t = os.path.getmtime(final)
        if v_t > f_t + 1:
            bad.append("final.mp4 比 voice.wav 旧 %s —— 跑 web/mux.py"
                       % gap(f_t, v_t))
            print("  [FAIL] %s" % bad[-1])
        else:
            print("  [OK]   成片比配音新（final %s）" % iso(f_t))
    else:
        warn.append("还没有 final.mp4")

    # ④ 顺手核对：台词字数大变过的话，配音大概率没跟上
    sp = os.path.join(d, "script.py")
    if os.path.exists(sp) and os.path.exists(tl_p):
        s_t = os.path.getmtime(sp)
        if s_t > v_t + 1:
            warn.append("script.py 比配音新 %s —— 改过台词就要重走 "
                        "gen_cues → tts_whole → gen_timeline → build_voice"
                        % gap(v_t, s_t))
            print("  [WARN] %s" % warn[-1])

    return 1 if bad else 0


def iso(t):
    import datetime
    return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M")


def gap(old, new):
    m = (new - old) / 60.0
    return "%.1f 分钟" % m if m < 600 else "%.1f 小时" % (m / 60)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    arg = sys.argv[1]
    if arg in ("全", "all"):
        names = sorted(n for n in os.listdir(MAKE)
                       if re.match(r"^\d{4}-\d{2}-\d{2}_", n)
                       and os.path.isdir(os.path.join(MAKE, n)))
    else:
        names = [arg.strip("/\\")]
    bad = sum(check_one(n) for n in names)
    print("=" * 60)
    print("共 %d 期，%d 期有问题" % (len(names), bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
