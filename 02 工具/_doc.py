# -*- coding: utf-8 -*-
"""_doc.py — 从 script.py 重新导出 文案.md（改完稿跑这一条）"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paths import proj_dir
from _rw import rewrite

name = sys.argv[1]
d = name if os.path.isdir(name) else proj_dir(name)
ns = {}
exec(compile(open(os.path.join(d, "script.py"), encoding="utf-8").read(), "s", "exec"), ns)
out = ["# %s · %s\n\n> %s\n" % (ns["NO"], ns["TITLE"], ns["SUBTITLE"]),
       "\n> **这份永远跟着 `script.py` 走，改了就地覆盖，不存多版。**\n"]
for sh in ns["SHOTS"]:
    out.append("\n## %s\n\n" % sh["id"])
    for ln in sh["lines"]:
        out.append(ln + "\n")
body = "".join(out)
out_p = os.path.join(d, "文案.md")
if os.path.exists(out_p):
    rewrite(out_p, body)          # 共享盘旧文件只读，走改名让位
else:
    io.open(out_p, "w", encoding="utf-8", newline="").write(body)
print("已更新", os.path.join(d, "文案.md"))
