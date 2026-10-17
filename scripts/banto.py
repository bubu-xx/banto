#!/usr/bin/env python3
"""banto の起動口。プラグインとして入れたときも、リポジトリを直接使うときも、ここから動かす。

  python3 scripts/banto.py --project <対象プロジェクト> sync
Windows では python3 の代わりに python。必要なもの: Python 3.10 以上、openpyxl（Excelを扱うとき）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

if sys.version_info < (3, 10):
    sys.exit("banto には Python 3.10 以上が必要です")

from banto.__main__ import main  # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(main())
    except ModuleNotFoundError as e:
        if e.name == "openpyxl":
            sys.exit("Excel を扱うには openpyxl が必要です: pip install openpyxl")
        raise
