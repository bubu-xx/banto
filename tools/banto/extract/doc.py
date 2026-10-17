"""設計書（MD / Excel）のテーブル定義表の1行を、列の事実に変換する共通処理。

表の形: 列名 / 型 / 制約（例: "PK, IDENTITY"、"NOT NULL, FK → types(id)"、"INDEX owners_last_name"）
設計書は表で全体を示しているので、書かれていない制約は「記載なし（なし）」として記録する。
"""
import re
from . import sqltype
from .ddl import CI_BY_DIALECT


def add_column(table, name, raw_type, constraints, loc, dialect=None):
    c = table.item(name.strip().strip("`").lower(), loc)
    raw_type = (raw_type or "").strip().strip("`")
    cons = [x.strip() for x in re.split(r"[,、]", constraints or "") if x.strip()]
    up = [x.upper() for x in cons]
    if raw_type:
        ty = sqltype.parse(raw_type)
        c.set("base_type", ty["base"], raw_type)
        if ty["base"] == "string":
            c.set("length", ty["length"], raw_type)
            ci = ty["ci"] if ty["ci"] is not None else CI_BY_DIALECT.get(dialect)
            if ci is not None:
                c.set("case_insensitive", ci, raw_type)
    pk = "PK" in up or "PRIMARY KEY" in up
    notnull = pk or any(u.startswith("NOT NULL") for u in up)
    c.set("nullable", not notnull, "NOT NULL" if notnull else "記載なし（NULL許容）")
    c.set("pk", pk, "PK" if pk else "記載なし")
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
    return c
