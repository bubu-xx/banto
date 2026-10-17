"""DDL（CREATE TABLE / ALTER TABLE / CREATE INDEX）からテーブル定義を取り出す。

対応: H2 / MySQL / PostgreSQL の一般的な書き方。書かれていることだけを事実とする。
DDLはテーブル全体が見えているので、書かれていない制約は「なし」として記録する。
"""
import re
from . import sqltype

# 表記から大文字小文字の区別が確定する方言だけ既定値を持つ。
# MySQL は照合順序で決まるため表記からは分からない（記録しない）。
CI_BY_DIALECT = {"h2": False, "postgres": False}


def _blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def _strip_comments(sql):
    sql = re.sub(r"/\*.*?\*/", _blank, sql, flags=re.S)
    return re.sub(r"--[^\n]*", _blank, sql)


def _split_top(body):
    parts, depth, cur, start = [], 0, "", 0
    for i, ch in enumerate(body):
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append((cur, start))
            cur, start = "", i + 1
        else:
            cur += ch
    if cur.strip():
        parts.append((cur, start))
    return parts


def _cols(s):
    return [c.strip().strip('`"').lower() for c in s.split(",") if c.strip()]


def extract(src, text, dialect, comment_as="logical_name"):
    sql = _strip_comments(text)

    def line(off):
        return f"{src.path}:{sql.count(chr(10), 0, off) + 1}"

    uniques, indexes = {}, {}
    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(", sql, re.I):
        depth, i = 1, m.end()
        while depth and i < len(sql):
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        body_start, body = m.end(), sql[m.end():i - 1]
        t = src.container(m.group(1).lower(), line(m.start()))
        uniques.setdefault(t.name, [])
        indexes.setdefault(t.name, [])
        opts = sql[i:sql.find(";", i) if sql.find(";", i) >= 0 else len(sql)]
        cm_ = re.search(r"COMMENT\s*=?\s*'((?:[^']|'')*)'", opts, re.I)
        if cm_:
            t.set("title" if comment_as == "logical_name" else "summary", cm_.group(1).replace("''", "'"),
                  f"COMMENT '{cm_.group(1)}'", line(m.start()))
        for item, off in _split_top(body):
            s = item.strip()
            if not s:
                continue
            iloc = line(body_start + off + (len(item) - len(item.lstrip())))
            if re.match(r"(PRIMARY\s+KEY|CONSTRAINT|FOREIGN\s+KEY|INDEX|KEY|UNIQUE)\b", s, re.I):
                _constraint(t, s, iloc, uniques, indexes)
                continue
            cm = re.match(r"[`\"]?(\w+)[`\"]?\s+([A-Za-z_]+(?:\s*\(\s*\d+\s*(?:,\s*\d+\s*)?\))?)(.*)", s, re.S)
            if cm:
                _column(t, cm.group(1).lower(), cm.group(2), cm.group(3), iloc, dialect, comment_as)

    for m in re.finditer(r"ALTER\s+TABLE\s+[`\"]?(\w+)[`\"]?\s+ADD\s+(.*?)(?:;|$)", sql, re.I | re.S):
        t = src.containers.get(m.group(1).lower())
        if t:
            _constraint(t, m.group(2), line(m.start()), uniques, indexes)

    for m in re.finditer(r"CREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[`\"]?(\w+)[`\"]?\s+)?ON\s+[`\"]?(\w+)[`\"]?\s*\(([^)]*)\)", sql, re.I):
        t = src.containers.get(m.group(3).lower())
        if not t:
            continue
        cols = _cols(m.group(4))
        if m.group(1):
            uniques[t.name].append((cols, line(m.start())))
        elif len(cols) > 1:
            indexes[t.name].append((cols, line(m.start())))
        c = t.items.get(cols[0])
        if c:
            c.set("indexed", True, f"INDEX {m.group(2) or '（名前なし）'}", line(m.start()))

    for m in re.finditer(r"COMMENT\s+ON\s+(TABLE|COLUMN)\s+([\w.\"`]+)\s+IS\s+'((?:[^']|'')*)'", sql, re.I):
        parts = [x.strip('"`').lower() for x in m.group(2).split(".")]
        text = m.group(3).replace("''", "'")
        if m.group(1).upper() == "TABLE":
            t = src.containers.get(parts[-1])
            if t:
                t.set("title" if comment_as == "logical_name" else "summary", text, f"COMMENT ON TABLE '{text}'", line(m.start()))
        elif len(parts) >= 2:
            t = src.containers.get(parts[-2])
            c = t.items.get(parts[-1]) if t else None
            if c:
                c.set(comment_as, text, f"COMMENT ON COLUMN '{text}'", line(m.start()))

    for t in src.containers.values():
        ix = sorted(indexes.get(t.name, []))
        t.set("indexes", "、".join("(" + ", ".join(k) + ")" for k, _ in ix),
              "、".join("INDEX(" + ", ".join(k) + ")" for k, _ in ix) or "複合インデックスなし",
              ix[0][1] if ix else t.loc)
        for c in t.items.values():
            pk = c.attrs.get("pk")
            if "indexed" not in c.attrs and not (pk and pk.value):
                c.set("indexed", False, "なし")
            if "fk" not in c.attrs:
                c.set("fk", "", "なし")
        u = sorted(uniques.get(t.name, []))
        t.set("unique", "、".join("(" + ", ".join(k) + ")" for k, _ in u),
              "、".join("UNIQUE(" + ", ".join(k) + ")" for k, _ in u) or "なし",
              u[0][1] if u else t.loc)


def _column(t, cname, raw, rest, loc, dialect, comment_as="logical_name"):
    c = t.item(cname, loc)
    ty = sqltype.parse(raw)
    if ty["base"] == "decimal":
        c.set("length", ty["length"], raw.strip())
        c.set("scale", ty["scale"], raw.strip())
    plain = re.sub(r"GENERATED\s+(?:ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY", "", rest, flags=re.I)
    dm = re.search(r"\bDEFAULT\s+('(?:[^']|'')*'|\([^)]*\)|[^\s,]+(?:\(\))?)", plain, re.I)
    dv = dm.group(1).strip("'").replace("''", "'") if dm else ""
    if dv.upper() == "NULL":
        dv = ""
    c.set("default", dv, f"DEFAULT {dm.group(1)}" if dm else "DEFAULT指定なし")
    cmm = re.search(r"\bCOMMENT\s+'((?:[^']|'')*)'", rest, re.I)
    if cmm:
        c.set(comment_as, cmm.group(1).replace("''", "'"), f"COMMENT '{cmm.group(1)}'")
    uns = bool(re.search(r"\bUNSIGNED\b", rest, re.I))
    shown = re.sub(r"\s+", " ", raw.strip()) + (" UNSIGNED" if uns else "")
    c.set("base_type", ty["base"], shown)
    if ty["base"] == "string":
        c.set("length", ty["length"], shown)
        ci = ty["ci"] if ty["ci"] is not None else CI_BY_DIALECT.get(dialect)
        if ci is not None:
            c.set("case_insensitive", ci, shown)
    if ty["base"] == "integer":
        c.set("unsigned", uns, "UNSIGNED" if uns else "UNSIGNED指定なし")
    pk = bool(re.search(r"PRIMARY\s+KEY", rest, re.I))
    notnull = pk or bool(re.search(r"NOT\s+NULL", rest, re.I))
    c.set("nullable", not notnull, "NOT NULL" if notnull else "NULL許容（NOT NULL指定なし）")
    c.set("pk", pk, "PRIMARY KEY" if pk else "なし")
    ident = bool(re.search(r"AUTO_INCREMENT|IDENTITY|\bSERIAL\b", rest + " " + raw, re.I))
    c.set("identity", ident, re.search(r"AUTO_INCREMENT|GENERATED[^,]*IDENTITY|IDENTITY|SERIAL", rest + " " + raw, re.I).group(0) if ident else "なし")
    rm = re.search(r"REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(\s*[`\"]?(\w+)", rest, re.I)
    if rm:
        tgt = f"{rm.group(1).lower()}.{rm.group(2).lower()}"
        c.set("fk", tgt, f"REFERENCES {tgt}")


def _constraint(t, s, loc, uniques, indexes=None):
    s = re.sub(r"^\s*CONSTRAINT\s+\w+\s+", "", s.strip(), flags=re.I)
    m = re.match(r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(([^)]*)\)", s, re.I)
    if m:
        c = t.items.get(_cols(m.group(1))[0])
        if c:
            tgt = f"{m.group(2).lower()}.{_cols(m.group(3))[0]}"
            c.set("fk", tgt, f"FOREIGN KEY → {tgt}", loc)
        return
    m = re.match(r"UNIQUE\s*(?:KEY|INDEX)?\s*\w*\s*\(([^)]*)\)", s, re.I)
    if m:
        uniques.setdefault(t.name, []).append((_cols(m.group(1)), loc))
        return
    m = re.match(r"(?:INDEX|KEY)\s*\w*\s*\(([^)]*)\)", s, re.I)
    if m:
        cols = _cols(m.group(1))
        if len(cols) > 1 and indexes is not None:
            indexes.setdefault(t.name, []).append((cols, loc))
        c = t.items.get(cols[0])
        if c:
            c.set("indexed", True, "INDEX（名前なし）", loc)
        return
    m = re.match(r"PRIMARY\s+KEY\s*\(([^)]*)\)", s, re.I)
    if m:
        for col in _cols(m.group(1)):
            c = t.items.get(col)
            if c:
                c.set("pk", True, "PRIMARY KEY", loc)
                c.set("nullable", False, "NOT NULL（主キー）", loc)
