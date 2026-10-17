"""SQLの型表記を、比較用の基本型・長さ・大文字小文字の区別に分解する。"""
import re

INTEGER = {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT", "SERIAL", "BIGSERIAL"}
STRING = {"VARCHAR", "CHAR", "CHARACTER", "TEXT", "VARCHAR_IGNORECASE", "NVARCHAR", "CLOB", "LONGTEXT", "MEDIUMTEXT"}
DATE = {"DATE"}
DECIMAL = {"DECIMAL", "NUMERIC", "NUMBER", "DEC"}
UNBOUNDED = {"TEXT", "CLOB", "LONGTEXT", "MEDIUMTEXT"}


def parse(raw):
    """戻り値: dict(base, length, scale, ci)。ci は表記から分かるときだけ True/False、分からなければ None。"""
    m = re.match(r"\s*([A-Za-z_]+)\s*(?:\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?", raw)
    name = m.group(1).upper() if m else raw.upper()
    num = int(m.group(2)) if m and m.group(2) else None
    sc = int(m.group(3)) if m and m.group(3) else None
    if name in INTEGER:
        return {"base": "integer", "length": None, "scale": None, "ci": None}
    if name in DATE:
        return {"base": "date", "length": None, "scale": None, "ci": None}
    if name in DECIMAL:
        return {"base": "decimal", "length": num, "scale": sc if sc is not None else (0 if num else None), "ci": None}
    if name in STRING:
        length = "unbounded" if name in UNBOUNDED else num
        ci = True if name == "VARCHAR_IGNORECASE" else None
        return {"base": "string", "length": length, "scale": None, "ci": ci}
    return {"base": name.lower(), "length": num, "scale": sc, "ci": None}


def show_length(v):
    return "無制限" if v == "unbounded" else str(v)
