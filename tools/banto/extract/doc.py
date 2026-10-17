"""設計書（MD / Excel）のテーブル定義表の1行を、列の事実に変換する共通処理。

表の見出しで列の意味を判断する（並び順は問わない）。見出しの別名は HEADERS。
設計書は表で全体を示しているので、制約の列があれば、書かれていない制約は「なし」として記録する。
論理名・説明・初期値などは、空欄なら「書かれていない」として扱う（台帳に人が書いた値と衝突させない）。
"""
import re
from . import sqltype
from .ddl import CI_BY_DIALECT

HEADERS = {
    "name": ("カラム", "列", "列名", "カラム名", "物理名", "項目物理名", "カラム物理名", "物理カラム名"),
    "type": ("型", "データ型", "型名"),
    "length": ("桁", "桁数", "長さ", "サイズ"),
    "scale": ("小数", "小数桁", "小数点以下桁数"),
    "constraints": ("制約", "制約条件"),
    "notnull": ("NOT NULL", "NOTNULL", "必須"),
    "pk": ("PK", "主キー"),
    "logical_name": ("論理名", "項目名", "カラム論理名", "論理カラム名", "項目論理名"),
    "description": ("説明", "備考"),
    "default": ("デフォルト", "初期値", "デフォルト値", "既定値"),
}
TRUTHY = {"○", "◯", "〇", "●", "Y", "YES", "TRUE", "1", "NOT NULL", "必須", "PK"}


def header_map(cells):
    """見出しの並びから {意味: 列番号} を作る。名前と型の列が無ければ None。"""
    out = {}
    for n, h in enumerate(cells):
        h = (h or "").strip().strip("`*")
        for k, names in HEADERS.items():
            if h in names and k not in out:
                out[k] = n
    return out if "name" in out and "type" in out else None


def add_row(table, cells, hmap, loc, dialect=None):
    def get(k):
        n = hmap.get(k)
        return (str(cells[n]).strip() if n is not None and n < len(cells) and cells[n] is not None else "")

    name = get("name").strip("`")
    if not name:
        return None
    c = table.item(name.lower(), loc)
    raw = get("type").strip("`")
    if raw:
        ty = sqltype.parse(raw)
        length = ty["length"]
        if length is None and get("length").isdigit():
            length = int(get("length"))
        scale = ty["scale"]
        if scale is None and get("scale").isdigit():
            scale = int(get("scale"))
        shown = raw + (f"（桁 {get('length')}）" if ty["length"] is None and get("length") else "")
        c.set("base_type", ty["base"], raw)
        if ty["base"] in ("string", "decimal") and length is not None:
            c.set("length", length, shown)
        if ty["base"] == "decimal" and scale is not None:
            c.set("scale", scale, shown)
        if ty["base"] == "string":
            ci = ty["ci"] if ty["ci"] is not None else CI_BY_DIALECT.get(dialect)
            if ci is not None:
                c.set("case_insensitive", ci, raw)
    cons_txt = get("constraints")
    cons = [x.strip() for x in re.split(r"[,、]", cons_txt) if x.strip()]
    up = [x.upper() for x in cons]
    has_cons = "constraints" in hmap
    pk = ("PK" in up or "PRIMARY KEY" in up) or get("pk").upper() in TRUTHY
    if has_cons or "pk" in hmap:
        c.set("pk", pk, "PK" if pk else "記載なし")
    if has_cons or "notnull" in hmap:
        notnull = pk or any(u.startswith("NOT NULL") for u in up) or get("notnull").upper() in TRUTHY
        c.set("nullable", not notnull, "NOT NULL" if notnull else "記載なし（NULL許容）")
    if has_cons:
        ident = any("IDENTITY" in u or "AUTO" in u for u in up)
        c.set("identity", ident, "IDENTITY" if ident else "記載なし")
        fk = next((x for x in cons if x.upper().startswith("FK")), None)
        m = re.search(r"`?(\w+)`?\s*\(\s*`?(\w+)", re.split(r"→|->", fk)[-1]) if fk else None
        if m:
            c.set("fk", f"{m.group(1).lower()}.{m.group(2).lower()}", fk.replace("`", ""))
        else:
            c.set("fk", "", "記載なし")
        idx = next((x for x in cons if x.upper().startswith("INDEX")), None)
        if not pk:
            c.set("indexed", bool(idx), idx.replace("`", "") if idx else "記載なし")
    if "default" in hmap:
        dv = get("default")
        c.set("default", "" if dv in ("", "-", "－", "なし", "NULL") else dv, dv or "記載なし")
    for k in ("logical_name", "description"):
        if get(k):
            c.set(k, get(k), get(k))
    return c


def add_column(table, name, raw_type, constraints, loc, dialect=None):
    """「列名 / 型 / 制約」の3列だけの表のための入口（後方互換）。"""
    return add_row(table, [name, raw_type, constraints], {"name": 0, "type": 1, "constraints": 2}, loc, dialect)
