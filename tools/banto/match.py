"""情報源どうしを突き合わせ、一致・片方にしかない・食い違いに仕分ける。

banto はどれが正かを決めない。ここで行うのは、事実の並べ替えと分類だけ。
"""
from collections import Counter
from dataclasses import dataclass, field
from .model import ATTRS

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Drift:
    kind: str                 # only-in | conflict
    table: str
    column: str | None
    attr: str                 # 属性名。存在のずれは "exists"
    severity: str
    values: list              # [(source, value, shown, loc)]  ※存在のずれは value=True/False
    group: str = ""
    group_label: str = ""
    id: str = ""
    extra: dict = field(default_factory=dict)


def _differing(values):
    """多数派の値と、それと違う情報源を返す。多数派は並べ方のための目安で、正しさの判定ではない。"""
    cnt = Counter(repr(v) for _, v, _, _ in values)
    top = max(cnt.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return top, sorted(s.id for s, v, _, _ in values if repr(v) != top)


def compare(sources):
    drifts, agreed = [], {}   # agreed[(table, col)][attr] = (value, shown, n_sources)
    order = {s.id: i for i, s in enumerate(sources)}
    all_tables = sorted({t for s in sources for t in s.tables})
    for tname in all_tables:
        having = [s for s in sources if tname in s.tables]
        if len(having) != len(sources):
            vals = [(s, tname in s.tables, "あり" if tname in s.tables else "記載なし",
                     s.tables[tname].loc if tname in s.tables else s.path) for s in sources]
            drifts.append(Drift("only-in", tname, None, "exists", "high", vals))
        cols = []
        for s in having:
            for c in s.tables[tname].columns:
                if c not in cols:
                    cols.append(c)
        for cname in cols:
            hc = [s for s in having if cname in s.tables[tname].columns]
            if len(hc) != len(having):
                vals = [(s, cname in s.tables[tname].columns,
                         "あり" if cname in s.tables[tname].columns else "記載なし",
                         s.tables[tname].columns[cname].loc if cname in s.tables[tname].columns else s.tables[tname].loc)
                        for s in having]
                drifts.append(Drift("only-in", tname, cname, "exists", "high", vals))
            for attr in ATTRS:
                vals = [(s, f.value, f.shown, f.loc) for s in hc
                        for f in [s.tables[tname].columns[cname].attrs.get(attr)] if f is not None]
                if not vals:
                    continue
                if len({repr(v) for _, v, _, _ in vals}) > 1:
                    drifts.append(Drift("conflict", tname, cname, attr, ATTRS[attr][1], vals))
                else:
                    agreed.setdefault((tname, cname), {})[attr] = (vals[0][1], vals[0][2], len(vals))
        # 複合の一意制約（DDLだけが表現する）
        ddl = [s for s in having if s.kind == "ddl"]
        if ddl:
            vals = [(s, tuple(sorted(k for k, _ in s.tables[tname].unique_keys)),
                     "、".join("UNIQUE(" + ", ".join(k) + ")" for k, _ in s.tables[tname].unique_keys) or "なし",
                     s.tables[tname].unique_keys[0][1] if s.tables[tname].unique_keys else s.tables[tname].loc) for s in ddl]
            if len({repr(v) for _, v, _, _ in vals}) > 1:
                drifts.append(Drift("conflict", tname, None, "unique", "low", vals))

    label = {s.id: s.label for s in sources}
    attr_name = {**{k: v[0] for k, v in ATTRS.items()}, "exists": "有無", "unique": "一意制約"}
    for d in drifts:
        if d.attr == "exists":
            missing = sorted((s.id for s, v, _, _ in d.values if not v), key=order.get)
            d.group = f"exists|{'table' if d.column is None else 'column'}|{','.join(missing)}"
            what = "テーブル" if d.column is None else "列"
            d.group_label = f"{what}が {'・'.join(label[m] for m in missing)} に無い"
        else:
            top, diff = _differing(d.values)
            diff = sorted(diff, key=order.get)
            dv = sorted({str(v) for s, v, _, _ in d.values if s.id in diff})
            d.group = f"{d.attr}|{','.join(diff)}|{'/'.join(dv)}"
            d.group_label = f"{attr_name[d.attr]}：{'・'.join(label[x] for x in diff)} が他と異なる"
    drifts.sort(key=lambda d: (SEVERITY_RANK[d.severity], d.group, d.table, d.column or "", d.attr))
    for i, d in enumerate(drifts, 1):
        d.id = f"DRF-{i:04d}"
    return drifts, agreed, attr_name
