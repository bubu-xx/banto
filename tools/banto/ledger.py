"""台帳（banto の原本となるMD）の読み書き。

1コンテナ（テーブル、テストクラス）につき1ファイル。人が直接読み書きでき、スクリプトも読み戻す。
機械が読む部分は <!-- banto:... --> の印の直後の表で、それ以外（メモなど）はそのまま残す。
"""
import os
import re
from dataclasses import dataclass, field
from . import frontmatter
from .domains.base import NONE
from . import fio

MARK = re.compile(r"\s*[⚠⏳]\[[A-Z]+-\d+\]\([^)]*\)")


@dataclass
class LItem:
    id: str
    name: str
    values: dict = field(default_factory=dict)   # 属性 -> 値（None は未定）
    exists: object = True                        # True / False（削除予定）/ None（有無が未定）
    free: dict = field(default_factory=dict)


@dataclass
class LContainer:
    id: str
    name: str
    status: str = "draft"            # draft | confirmed | pending（有無が未定）| removing | removed
    attrs: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)   # 名前 -> LItem（並び順を保つ）
    allowed: dict = field(default_factory=dict)  # key -> {source_id: (値, DEC)}
    notes: str = ""

    @property
    def exists(self):
        if self.status == "pending":
            return None
        return self.status not in ("removing", "removed")


def _cells(line):
    out, cur, esc = [], "", False
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    for ch in s:
        if ch == "\\" and not esc:
            esc = True
            cur += ch
            continue
        if ch == "|" and not esc:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        esc = False
    out.append(cur.strip())
    return out


def _table_after(lines, marker):
    """印の直後の表を、(見出し, 行のリスト) で返す。"""
    try:
        i = next(n for n, ln in enumerate(lines) if ln.strip() == marker)
    except StopIteration:
        return None, []
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        i += 1
    if i >= len(lines):
        return None, []
    head = _cells(lines[i])
    rows = []
    j = i + 2
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        rows.append(_cells(lines[j]))
        j += 1
    return head, rows


def _plain(cell):
    """台帳のセルから、bantoが付けた印（⚠[DRF-…](…)）を取り除いた値の文字列。"""
    return MARK.sub("", cell).strip()


def _name(cell):
    return _plain(cell).strip("`")


def load(path, domain):
    meta, body = frontmatter.load(fio.read(path))
    lines = body.splitlines()
    c = LContainer(meta.get("doc_id", ""), meta.get("container", ""), meta.get("status", "draft"))
    head, rows = _table_after(lines, "<!-- banto:attrs -->")
    labels = {a.label: a for a in domain.container_attrs()}
    for r in rows:
        if len(r) >= 2 and r[0] in labels:
            v = labels[r[0]].parse(_plain(r[1]))
            if v is not None:
                c.attrs[labels[r[0]].name] = v
    head, rows = _table_after(lines, "<!-- banto:items -->")
    if head:
        cols = {h: n for n, h in enumerate(head)}
        attr_by_label = {a.label: a for a in domain.item_attrs()}
        for r in rows:
            r = r + [""] * (len(head) - len(r))
            name = _name(r[cols[domain.item_label]])
            it = LItem(_name(r[cols["ID"]]), name)
            for h, n in cols.items():
                if h in attr_by_label:
                    v = attr_by_label[h].parse(_plain(r[n]))
                    if v is not None:
                        it.values[attr_by_label[h].name] = v
                elif h in domain.free_columns:
                    it.free[h] = r[n]
            st = r[cols.get("状態", len(r) - 1)]
            it.exists = None if "有無未定" in st else ("削除予定" not in st)
            c.items[name] = it
    head, rows = _table_after(lines, "<!-- banto:allowed -->")
    if head:
        by_id = {it.id: it.name for it in c.items.values()}
        for r in rows:
            if len(r) < 5:
                continue
            target, label, src, val, dec = (_plain(x) for x in r[:5])
            item = by_id.get(target)
            attr = domain.attr("exists") if label == "有無" else next(
                (a for a in domain.attrs.values() if a.label == label), None)
            if attr is None:
                continue
            k = f"{domain.name}|{c.name}|{item or ''}|{attr.name}"
            c.allowed.setdefault(k, {})[src] = (attr.parse(val), dec)
    m = re.search(r"<!-- banto:notes -->\n?(.*)$", body, re.S)
    if m:
        c.notes = m.group(1).strip("\n")
    return c


def load_all(base, domain):
    d = os.path.join(base, domain.ledger_dir)
    out = {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.endswith(".md") and f != "README.md":
            c = load(os.path.join(d, f), domain)
            if c.name:
                out[c.name] = c
    return out


def file_name(name):
    return re.sub(r"[^\w.-]", "_", name) + ".md"
