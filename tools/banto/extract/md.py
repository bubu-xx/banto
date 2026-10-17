"""MD設計書から、見出し（`テーブル名`）直下の「カラム / 型 / 制約」表を取り出す。"""
import re
from .doc import add_column

HEAD = re.compile(r"^#{2,6}\s+`?(\w+)`?\s*(?:[（(].*)?$")
NAME_HEADERS = ("カラム", "列", "列名", "カラム名")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def extract(src, text, dialect=None):
    lines = text.splitlines()
    current, i = None, 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if m:
            current = (m.group(1).lower(), i + 1)
        elif lines[i].lstrip().startswith("|") and current and cells(lines[i])[0] in NAME_HEADERS:
            t = src.container(current[0], f"{src.path}:{current[1]}")
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                c = cells(lines[j]) + ["", "", ""]
                add_column(t, c[0], c[1], c[2], f"{src.path}:{j + 1}", dialect)
                j += 1
            current, i = None, j
            continue
        i += 1
