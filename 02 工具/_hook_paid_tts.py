# -*- coding: utf-8 -*-
"""把 tts_whole.py 接上付费引擎（--engine minimax|doubao）"""
import io
import os
import sys

TOOL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOL)
from _rw import patch  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else \
    r"\\192.168.1.3\Naonao\30 制作\NO.17_等一句话\tts_whole.py"

PAIRS = [
    # 1) 引擎开关 + 工具目录
    (
        'VOICE = "zh-CN-YunyangNeural"\nRATE = "+8%"',
        'ENGINE = os.environ.get("TTS_ENGINE", "edge")   # edge / minimax / doubao\n'
        '_TOOLS = os.path.abspath(os.path.join(_HERE, "..", "..", "02 工具"))\n'
        'if os.path.isdir(_TOOLS) and _TOOLS not in sys.path:\n'
        '    sys.path.insert(0, _TOOLS)\n\n'
        'VOICE = "zh-CN-YunyangNeural"\nRATE = "+8%"',
    ),
    # 2) synth 分流
    (
        '    """整段合成；返回句子边界 [(t0, t1, txt)]（秒）。失败自动重试。\n\n'
        '    不走 te.synth_edge：它会在共享盘上 os.remove(mp3)，\n'
        '    而这台机器的 safe-delete 对 192.168.1.3 会失败并抛异常。\n'
        '    """\n'
        '    import edge_tts\n',
        '    """整段合成；返回句子边界 [(t0, t1, txt)]（秒）。失败自动重试。\n\n'
        '    不走 te.synth_edge：它会在共享盘上 os.remove(mp3)，\n'
        '    而这台机器的 safe-delete 对 192.168.1.3 会失败并抛异常。\n\n'
        '    ENGINE != edge 时交给 02 工具/_tts_paid.py（MiniMax / 豆包），\n'
        '    契约相同：返回 [[t0,t1,文本]] 或 None（None -> 静音兜底）。\n'
        '    """\n'
        '    if ENGINE != "edge":\n'
        '        import _tts_paid as tp\n'
        '        return await asyncio.get_event_loop().run_in_executor(\n'
        '            None, tp.synth, text, path, ENGINE, None)\n'
        '    import edge_tts\n',
    ),
    # 3) 缓存键带上引擎（换引擎不能复用旧时间码）
    (
        '        sp = os.path.join(tmp, key + ".sents.json")',
        '        sp = os.path.join(tmp, key + "." + ENGINE + ".sents.json")',
    ),
    (
        '        json.dump(s, open(os.path.join(tmp, key + ".sents.json"), "w",\n'
        '                          encoding="utf-8"), ensure_ascii=False)',
        '        json.dump(s, open(os.path.join(tmp, key + "." + ENGINE + ".sents.json"), "w",\n'
        '                          encoding="utf-8"), ensure_ascii=False)',
    ),
    # 4) 命令行参数
    (
        '    ap.add_argument("--fresh", action="store_true", help="忽略缓存全部重合成")\n'
        '    a = ap.parse_args()',
        '    ap.add_argument("--fresh", action="store_true", help="忽略缓存全部重合成")\n'
        '    ap.add_argument("--engine", default=None,\n'
        '                    choices=["edge", "minimax", "doubao"],\n'
        '                    help="合成引擎，默认读环境变量 TTS_ENGINE 或 edge")\n'
        '    a = ap.parse_args()\n'
        '    global ENGINE\n'
        '    if a.engine:\n'
        '        ENGINE = a.engine',
    ),
]

patch(TARGET, PAIRS)
print("已改:", TARGET)
print(io.open(TARGET, encoding="utf-8").read()[:0] or "ok")
