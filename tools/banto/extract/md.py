"""MD設計書から、見出し（`テーブル名`）直下の「カラム / 型 / 制約」表を取り出す。"""
import re
from .doc import add_column
from ..model import Source

HEAD = re.compile(r"^#{2,6}\s+`?(\w+)`?\s*(?:[（(].*)?$")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def extract(src: Source, text, dialect=None):
    lines = text.splitlines()
    current = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = HEAD.match(ln)
        if m:
            current = (m.group(1).lower(), i + 1)
        elif ln.lstrip().startswith("|") and current:
            header = _cells(ln)
            if header and header[0] in ("カラム", "列", "列名", "カラム名"):
                t = src.table(current[0], f"{src.path}:{current[1]}")
                j = i + 2  # 区切り行を飛ばす
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    cells = _cells(lines[j]) + ["", "", ""]
                    add_column(t, cells[0], cells[1].strip("`"), cells[2], f"{src.path}:{j + 1}", dialect)
                    j += 1
                current = None
                i = j
                continue
        i += 1
