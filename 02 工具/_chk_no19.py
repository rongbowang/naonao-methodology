# -*- coding: utf-8 -*-
"""_chk_no19.py — NO.19《地球加长一米》画面文档体检（8 项）

用法：python "02 工具/_chk_no19.py"
（实际逻辑在 _chkdoc.py，本文件只是锁定期号，方便直接跑）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chkdoc import main  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__":
    sys.exit(main(os.path.join(ROOT, "30 制作", "NO.19_地球加长一米")))
