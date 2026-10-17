"""領域: テーブル定義（コンテナ = テーブル、項目 = 列）"""
import os
from .base import Attr, Domain
from ..extract import ddl, md, xlsx, jpa
from .. import fio

DOMAIN = Domain(
    name="tables", title="テーブル定義書", container_label="テーブル", item_label="列",
    container_prefix="TBL", item_prefix="COL", ledger_dir="design/detail/tables", exists_severity="high",
    attrs={a.name: a for a in [
        Attr("base_type", "型", "high"),
        Attr("length", "長さ", "medium", "length"),
        Attr("nullable", "NULL", "high", "nullable"),
        Attr("pk", "PK", "high", "bool"),
        Attr("fk", "FK", "high", "fk"),
        Attr("indexed", "INDEX", "low", "bool"),
        Attr("identity", "自動採番", "low", "bool"),
        Attr("case_insensitive", "大小区別", "medium", "ci"),
        Attr("unsigned", "符号なし", "low", "bool"),
        Attr("unique", "一意制約", "low", "text", scope="container"),
    ]},
)


def extract(src, cfg, project):
    full = os.path.join(project, cfg["path"])
    kind = cfg["kind"]
    if kind == "ddl":
        ddl.extract(src, fio.read(full), cfg.get("dialect"))
    elif kind == "md":
        md.extract(src, fio.read(full), cfg.get("dialect"))
    elif kind == "xlsx":
        xlsx.extract(src, full, cfg["sheet"], cfg.get("dialect"))
    elif kind == "jpa":
        jpa.extract(src, full, project)
    else:
        raise ValueError(f"テーブル定義で未対応の情報源の種類: {kind}")
