"""対象プロジェクトの banto/sources.json を読み、各情報源からテーブル定義を取り出す。"""
import json
import os
from .model import Source
from .extract import ddl, md, xlsx, jpa


def load(project):
    cfg = json.load(open(os.path.join(project, "banto", "sources.json"), encoding="utf-8"))
    out = []
    for s in cfg["tables"]:
        src = Source(s["id"], s["label"], s["kind"], s["path"], scope_note=s.get("scope_note", ""))
        full = os.path.join(project, s["path"])
        if s["kind"] == "ddl":
            ddl.extract(src, open(full, encoding="utf-8").read(), s.get("dialect"))
        elif s["kind"] == "md":
            md.extract(src, open(full, encoding="utf-8").read(), s.get("dialect"))
        elif s["kind"] == "xlsx":
            xlsx.extract(src, full, s["sheet"], s.get("dialect"))
        elif s["kind"] == "jpa":
            jpa.extract(src, full, project)
        else:
            raise ValueError(f"未対応の情報源の種類: {s['kind']}")
        out.append(src)
    return out


def dump(sources):
    """抽出結果を、比較・再現用にJSONへ落とす。"""
    return {
        s.id: {
            "label": s.label, "kind": s.kind, "path": s.path,
            "tables": {
                t.name: {
                    "loc": t.loc,
                    "unique_keys": [{"columns": list(k), "loc": l} for k, l in t.unique_keys],
                    "columns": {
                        c.name: {a: {"value": f.value, "shown": f.shown, "loc": f.loc} for a, f in sorted(c.attrs.items())}
                        for c in t.columns.values()
                    },
                } for t in sorted(s.tables.values(), key=lambda t: t.name)
            },
        } for s in sources
    }
