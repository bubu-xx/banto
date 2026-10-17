"""JPAエンティティ（Java）から、マッピングされるテーブルと列を取り出す。

書かれている注釈だけを事実とする:
  @Table / @Column(name, length) / @Id / @GeneratedValue(IDENTITY)
  @ManyToOne・@OneToMany + @JoinColumn / @ManyToMany + @JoinTable
  @NotBlank・@NotNull・@NotEmpty（アプリ側の必須）/ @Size(max) / @Pattern(\\d{n})
列名は Spring Boot 既定の物理命名（キャメルケース → スネークケース）で導く。
"""
import os
import re
from ..model import Source

SIMPLE = {"Integer": "integer", "int": "integer", "Long": "integer", "long": "integer",
          "String": "string", "LocalDate": "date", "Date": "date", "LocalDateTime": "datetime"}


def snake(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def _arg(ann, key):
    m = re.search(key + r"\s*=\s*\"([^\"]*)\"", ann)
    return m.group(1) if m else None


def _parse_file(path, rel):
    lines = open(path, encoding="utf-8").read().splitlines()
    cls, pending, fields = None, [], []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("@"):
            ann, start = s, i
            while ann.count("(") > ann.count(")") and i + 1 < len(lines):
                i += 1
                ann += " " + lines[i].strip()
            pending.append((ann, start + 1))
        elif re.match(r"(public\s+)?(abstract\s+)?class\s+\w+", s):
            m = re.match(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?", s)
            cls = {"name": m.group(1), "extends": m.group(2), "anns": pending, "line": i + 1}
            pending = []
        elif cls and re.match(r"(private|protected|public)\s", s) and s.endswith(";") and "(" not in s.split("=")[0]:
            m = re.match(r"(?:private|protected|public)\s+((?:final|static|transient)\s+)*([\w<>, ?]+?)\s+(\w+)\s*(?:=.*)?;", s)
            if m and "static" not in (m.group(1) or "") and not any(a.startswith("@Transient") for a, _ in pending):
                fields.append({"type": m.group(2).strip(), "name": m.group(3), "anns": pending, "line": i + 1})
            pending = []
        elif s and not s.startswith(("//", "*", "/*", "import", "package")):
            if not s.startswith("@"):
                pending = []
        i += 1
    if cls:
        cls["fields"], cls["path"] = fields, rel
    return cls


def extract(src: Source, root, base_dir):
    classes = {}
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.endswith(".java"):
                p = os.path.join(dp, f)
                c = _parse_file(p, os.path.relpath(p, base_dir).replace(os.sep, "/"))
                if c:
                    classes[c["name"]] = c

    def has(c, name):
        return any(a.startswith("@" + name) for a, _ in c["anns"])

    entities = {n: c for n, c in classes.items() if has(c, "Entity")}
    table_of = {}
    for n, c in entities.items():
        tann = next((a for a, _ in c["anns"] if a.startswith("@Table")), "")
        table_of[n] = (_arg(tann, "name") or snake(n)).lower()

    def chain(c):
        out = []
        while c:
            out.insert(0, c)
            c = classes.get(c["extends"]) if c["extends"] else None
        return out

    for n, ent in sorted(entities.items()):
        t = src.table(table_of[n], f"{ent['path']}:{ent['line']}")
        for k in chain(ent):
            for f in k["fields"]:
                _field(src, t, n, f, k["path"], table_of)


def _field(src, t, owner, f, path, table_of):
    anns = {a.split("(")[0].lstrip("@"): (a, ln) for a, ln in f["anns"]}
    loc = f"{path}:{f['line']}"
    inner = re.search(r"<\s*(\w+)\s*>", f["type"])
    elem = inner.group(1) if inner else f["type"]

    if "ManyToOne" in anns or "OneToOne" in anns:
        jc = anns.get("JoinColumn", ("", 0))[0]
        name = (_arg(jc, "name") or snake(f["name"]) + "_id").lower()
        c = t.col(name, loc)
        c.set("base_type", "integer", f"{f['type']} {f['name']}（@ManyToOne）")
        if elem in table_of:
            c.set("fk", f"{table_of[elem]}.id", f"@ManyToOne → {table_of[elem]}.id")
        return
    if "OneToMany" in anns:
        jc = anns.get("JoinColumn")
        if jc and elem in table_of:
            name = _arg(jc[0], "name").lower()
            other = src.table(table_of[elem], loc)
            c = other.col(name, f"{path}:{jc[1]}")
            c.set("base_type", "integer", f"@OneToMany @JoinColumn(name=\"{name}\")（{owner}.{f['name']}）")
            c.set("fk", f"{t.name}.id", f"@OneToMany @JoinColumn → {t.name}.id")
        return
    if "ManyToMany" in anns:
        jt = anns.get("JoinTable")
        if jt and elem in table_of:
            a = jt[0]
            jname = _arg(a, "name").lower()
            jcols = re.findall(r"@JoinColumn\(\s*name\s*=\s*\"(\w+)\"", a)
            jtab = src.table(jname, f"{path}:{jt[1]}")
            for cname, tgt in zip(jcols, [t.name, table_of[elem]]):
                c = jtab.col(cname.lower(), f"{path}:{jt[1]}")
                c.set("base_type", "integer", f"@JoinTable({jname}).{cname}")
                c.set("fk", f"{tgt}.id", f"@JoinTable → {tgt}.id")
        return
    if f["type"] not in SIMPLE:
        return

    col_ann = anns.get("Column", ("", 0))[0]
    name = (_arg(col_ann, "name") or snake(f["name"])).lower()
    c = t.col(name, loc)
    c.set("base_type", SIMPLE[f["type"]], f"{f['type']} {f['name']}")
    if "Id" in anns:
        c.set("pk", True, "@Id")
        c.set("nullable", False, "@Id")
        gv = anns.get("GeneratedValue", ("", 0))[0]
        if "IDENTITY" in gv:
            c.set("identity", True, "@GeneratedValue(IDENTITY)")
    req = next((k for k in ("NotBlank", "NotNull", "NotEmpty") if k in anns), None)
    if req and "Id" not in anns:
        c.set("nullable", False, f"@{req}（アプリ側の必須検証）")
    lm = re.search(r"length\s*=\s*(\d+)", col_ann)
    sz = re.search(r"max\s*=\s*(\d+)", anns.get("Size", ("", 0))[0])
    pt = re.search(r"regexp\s*=\s*\"\\\\d\{(\d+)\}\"", anns.get("Pattern", ("", 0))[0])
    if lm:
        c.set("length", int(lm.group(1)), f"@Column(length={lm.group(1)})")
    elif sz:
        c.set("length", int(sz.group(1)), f"@Size(max={sz.group(1)})")
    elif pt:
        c.set("length", int(pt.group(1)), f"@Pattern(\\d{{{pt.group(1)}}})（{pt.group(1)}桁固定）")
