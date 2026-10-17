"""DDL（CREATE TABLE / ALTER TABLE / CREATE INDEX）からテーブル定義を取り出す。

対応: H2 / MySQL / PostgreSQL の一般的な書き方。方言ごとの意味づけは最小限にとどめ、
書かれていることだけを事実として取り出す。
"""
import re
from . import sqltype
from ..model import Source

CI_BY_DIALECT = {
    # 表記から大文字小文字の区別が確定する方言だけ既定値を持つ。
    # MySQL は照合順序で決まるため表記からは分からない（None）。
    "h2": False,
    "postgres": False,
}


def _strip_comments(sql):
    sql = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), sql, flags=re.S)
    return re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), sql)


def _split_top(body):
    parts, depth, cur, start = [], 0, "", 0
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append((cur, start))
            cur, start = "", i + 1
        else:
            cur += ch
    if cur.strip():
        parts.append((cur, start))
    return parts


def _cols(s):
    return [c.strip().strip('`"') for c in s.split(",")]


def extract(src: Source, text, dialect):
    sql = _strip_comments(text)

    def line(off):
        return f"{src.path}:{sql.count(chr(10), 0, off) + 1}"

    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(", sql, re.I):
        tname = m.group(1).lower()
        # 対応する閉じ括弧を探す
        depth, i = 1, m.end()
        while depth and i < len(sql):
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        body_start = m.end()
        body = sql[body_start:i - 1]
        t = src.table(tname, line(m.start()))
        for item, off in _split_top(body):
            s = item.strip()
            iloc = line(body_start + off + (len(item) - len(item.lstrip())))
            up = s.upper()
            if up.startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "INDEX", "KEY", "UNIQUE")):
                _table_constraint(t, s, iloc)
                continue
            cm = re.match(r"[`\"]?(\w+)[`\"]?\s+([A-Za-z_]+(?:\s*\(\s*\d+\s*\))?)(.*)", s, re.S)
            if not cm:
                continue
            cname, raw, rest = cm.group(1).lower(), cm.group(2), cm.group(3)
            c = t.col(cname, iloc)
            ty = sqltype.parse(raw)
            shown = re.sub(r"\s+", " ", (raw + (" UNSIGNED" if re.search(r"\bUNSIGNED\b", rest, re.I) else "")).strip())
            c.set("base_type", ty["base"], shown)
            if ty["base"] == "string":
                c.set("length", ty["length"], shown)
                ci = ty["ci"] if ty["ci"] is not None else CI_BY_DIALECT.get(dialect)
                if ci is not None:
                    c.set("case_insensitive", ci, shown)
            if ty["base"] == "integer":
                uns = bool(re.search(r"\bUNSIGNED\b", rest, re.I))
                c.set("unsigned", uns, "UNSIGNED" if uns else "符号あり（UNSIGNED指定なし）")
            pk = bool(re.search(r"PRIMARY\s+KEY", rest, re.I))
            notnull = bool(re.search(r"NOT\s+NULL", rest, re.I)) or pk
            c.set("nullable", not notnull, "NOT NULL" if notnull else "NULL許容")
            c.set("pk", pk, "PRIMARY KEY" if pk else "なし")
            ident = bool(re.search(r"AUTO_INCREMENT|IDENTITY|\bSERIAL\b", rest + " " + raw, re.I))
            c.set("identity", ident, "自動採番" if ident else "なし")
            rm = re.search(r"REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(\s*[`\"]?(\w+)", rest, re.I)
            if rm:
                tgt = f"{rm.group(1).lower()}.{rm.group(2).lower()}"
                c.set("fk", tgt, f"REFERENCES {tgt}")

    for m in re.finditer(r"ALTER\s+TABLE\s+[`\"]?(\w+)[`\"]?\s+ADD\s+(.*?)(?:;|$)", sql, re.I | re.S):
        t = src.tables.get(m.group(1).lower())
        if t:
            _table_constraint(t, m.group(2), line(m.start()))

    for m in re.finditer(r"CREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[`\"]?(\w+)[`\"]?\s+)?ON\s+[`\"]?(\w+)[`\"]?\s*\(([^)]*)\)", sql, re.I):
        t = src.tables.get(m.group(3).lower())
        if not t:
            continue
        cols = [c.lower() for c in _cols(m.group(4))]
        name = m.group(2) or "（名前なし）"
        if m.group(1):
            t.unique_keys.append((tuple(cols), line(m.start())))
        c = t.columns.get(cols[0])
        if c:
            c.set("indexed", True, f"INDEX {name}", line(m.start()))

    # 明示されたインデックスが無い列は「インデックスなし」と記録する（DDLは全体が見えているため）
    for t in src.tables.values():
        for c in t.columns.values():
            pk = c.attrs.get("pk")
            if "indexed" not in c.attrs and not (pk and pk.value):
                c.set("indexed", False, "なし")


def _table_constraint(t, s, loc):
    s = re.sub(r"^\s*CONSTRAINT\s+\w+\s+", "", s.strip(), flags=re.I)
    m = re.match(r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(([^)]*)\)", s, re.I)
    if m:
        col, tgt = _cols(m.group(1))[0].lower(), f"{m.group(2).lower()}.{_cols(m.group(3))[0].lower()}"
        c = t.columns.get(col)
        if c:
            c.set("fk", tgt, f"FOREIGN KEY → {tgt}", loc)
        return
    m = re.match(r"UNIQUE\s*(?:KEY|INDEX)?\s*\w*\s*\(([^)]*)\)", s, re.I)
    if m:
        t.unique_keys.append((tuple(c.lower() for c in _cols(m.group(1))), loc))
        return
    m = re.match(r"(?:INDEX|KEY)\s*\w*\s*\(([^)]*)\)", s, re.I)
    if m:
        c = t.columns.get(_cols(m.group(1))[0].lower())
        if c:
            c.set("indexed", True, "INDEX（名前なし）", loc)
        return
    m = re.match(r"PRIMARY\s+KEY\s*\(([^)]*)\)", s, re.I)
    if m:
        for col in _cols(m.group(1)):
            c = t.columns.get(col.lower())
            if c:
                c.set("pk", True, "PRIMARY KEY", loc)
                c.set("nullable", False, "NOT NULL（主キー）", loc)
