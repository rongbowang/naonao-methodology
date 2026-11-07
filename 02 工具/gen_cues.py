# -*- coding: utf-8 -*-
"""从 script.py 的 SHOTS 生成 cues.json（逐句 TTS 的输入）

用法:
    python gen_cues.py            # 默认处理当前目录的 script.py
    python gen_cues.py v6_moon    # 处理指定项目目录

输出: <项目>/cues.json  ->  [{"id": "<shot>_c00", "text": "..."}, ...]
"""
import json
import os
import sys


def build(proj_dir):
    sys.path.insert(0, os.path.abspath(proj_dir))
    import importlib
    for m in list(sys.modules):
        if m == "script":
            del sys.modules[m]
    import script  # noqa: E402

    # 逐句音色/情绪覆盖：script.py 里的两张表，键是 "<镜头id>_c<句号>" 或 "<镜头id>"
    vmap = getattr(script, "VOICE_MAP", {}) or {}
    emap = getattr(script, "EMOTION_MAP", {}) or {}
    cues = []
    for sh in script.SHOTS:
        for i, line in enumerate(sh["lines"]):
            cid = "%s_c%02d" % (sh["id"], i)
            # line 可以是纯字符串，也可以是 {"text":..., "voice":..., "emotion":...}
            if isinstance(line, dict):
                c = {"id": cid, "text": line["text"]}
                for k in ("voice", "emotion", "speed", "pitch"):
                    if line.get(k):
                        c[k] = line[k]
            else:
                c = {"id": cid, "text": line}
            # 合并覆盖表：EMOTION_MAP 可按镜头 id 给整镜默认情绪，VOICE_MAP 按句覆盖
            emo = emap.get(sh["id"])
            if emo and "emotion" not in c:
                c["emotion"] = emo
            ov = vmap.get(cid)
            if ov:
                c.update({k: v for k, v in ov.items() if v})
            cues.append(c)

    out = os.path.join(proj_dir, "cues.json")
    _txt = json.dumps(cues, ensure_ascii=False, indent=1)
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(_txt)
    except PermissionError:       # 共享盘老文件只读 -> 走 rename 绕法
        from _rw import rewrite
        rewrite(out, _txt)
    print("wrote %s : %d cues / %d shots"
          % (out, len(cues), len(script.SHOTS)))
    return cues


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "."
    if os.path.isdir(a):
        d = a
    else:                       # 传的是期名（NO.17_等一句话），走统一路径解析
        from _paths import proj_dir
        d = proj_dir(a)
    build(d)
