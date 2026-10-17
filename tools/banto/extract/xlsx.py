"""Excel設計書から、「テーブル: 名前」行に続く「カラム / 型 / 制約」表を取り出す。"""
from .doc import add_column

NAME_HEADERS = ("カラム", "列", "列名", "カラム名")


def extract(src, path, sheet, dialect=None):
    import openpyxl  # Excelの情報源があるときだけ必要
    ws = openpyxl.load_workbook(path, data_only=True)[sheet]
    rows = list(ws.iter_rows())
    i = 0
    while i < len(rows):
        a = rows[i][0]
        v = str(a.value or "")
        if v.startswith(("テーブル:", "テーブル：")):
            t = src.container(v.replace("：", ":").split(":", 1)[1].strip().lower(), f"{src.path}!{sheet}!{a.coordinate}")
            j = i + 1
            while j < len(rows) and str(rows[j][0].value or "").strip() not in NAME_HEADERS:
                j += 1
            j += 1
            while j < len(rows) and rows[j][0].value not in (None, ""):
                r = rows[j]
                val = lambda k: str(r[k].value) if len(r) > k and r[k].value is not None else ""
                add_column(t, val(0), val(1), val(2), f"{src.path}!{sheet}!{r[0].coordinate}", dialect)
                j += 1
            i = j
            continue
        i += 1
