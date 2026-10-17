"""Excel設計書から、「テーブル: 名前」行に続くテーブル定義表を取り出す。

表の見出し行（名前と型の列を含む行）を探し、見出しで列の意味を判断する（doc.HEADERS）。
「テーブル: 飼い主（owners）」のように論理名が添えてあれば、それも取り出す。
"""
import re
from .doc import add_row, header_map


def extract(src, path, sheet, dialect=None):
    import openpyxl  # Excelの情報源があるときだけ必要
    ws = openpyxl.load_workbook(path, data_only=True)[sheet]
    rows = [[c.value for c in r] for r in ws.iter_rows()]
    coords = [[c.coordinate for c in r] for r in ws.iter_rows()]
    i = 0
    while i < len(rows):
        v = str(rows[i][0] or "")
        if v.startswith(("テーブル:", "テーブル：")):
            title = v.replace("：", ":").split(":", 1)[1].strip()
            m = re.search(r"[（(]([A-Za-z_]\w*)[)）]", title)
            name, logical = (m.group(1), title[:m.start()].strip()) if m else (title, None)
            t = src.container(name.lower(), f"{src.path}!{sheet}!{coords[i][0]}")
            if logical:
                t.set("title", logical, logical)
            j, hmap = i + 1, None
            while j < len(rows) and j < i + 6:
                hmap = header_map([str(x) if x is not None else "" for x in rows[j]])
                if hmap:
                    break
                j += 1
            if not hmap:
                i += 1
                continue
            j += 1
            while j < len(rows) and rows[j][hmap["name"]] not in (None, ""):
                add_row(t, rows[j], hmap, f"{src.path}!{sheet}!{coords[j][0]}", dialect)
                j += 1
            i = j
            continue
        i += 1
