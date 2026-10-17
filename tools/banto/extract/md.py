"""MD設計書から、見出し直下のテーブル定義表を取り出す。

見出しの形: `#### owners`、`#### `owners``、`#### 飼い主（owners）` のどれでもよい。
表の見出しで列の意味を判断する（doc.HEADERS）。
"""
import re
from .doc import add_row, header_map

HEAD = re.compile(r"^#{2,6}\s+(.*?)\s*$")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table_name(title):
    """見出しの文字列から、テーブルの物理名と（あれば）論理名を取り出す。"""
    m = re.search(r"[（(]`?([A-Za-z_]\w*)`?[)）]", title)
    if m:
        logical = title[:m.start()].strip().strip("`")
        return m.group(1).lower(), (logical or None)
    m = re.fullmatch(r"`?([A-Za-z_]\w*)`?(?:\s*[（(].*[)）])?", title)
    if m:
        return m.group(1).lower(), None
    return None, None


def extract(src, text, dialect=None):
    lines = text.splitlines()
    current, i = None, 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if m:
            name, logical = _table_name(m.group(1))
            current = (name, logical, i + 1) if name else None
        elif lines[i].lstrip().startswith("|") and current:
            hmap = header_map(cells(lines[i]))
            if hmap:
                t = src.container(current[0], f"{src.path}:{current[2]}")
                if current[1]:
                    t.set("title", current[1], current[1])
                j = i + 2
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    add_row(t, cells(lines[j]), hmap, f"{src.path}:{j + 1}", dialect)
                    j += 1
                current, i = None, j
                continue
        i += 1
