"""領域: テーブル定義（コンテナ = テーブル、項目 = 列）

manual=True の属性は、情報源にあれば取り込み、無ければ人が台帳に書く（論理名・説明など）。
"""
import os
from .base import Attr, Domain
from .. import fio
from ..extract import ddl, md, xlsx, jpa

DOMAIN = Domain(
    name="tables", title="テーブル定義書", container_label="テーブル", item_label="列",
    container_prefix="TBL", item_prefix="COL", ledger_dir="design/detail/tables", exists_severity="high",
    attrs={a.name: a for a in [
        Attr("logical_name", "論理名", "low"),
        Attr("base_type", "型", "high"),
        Attr("length", "長さ", "medium", "length"),
        Attr("scale", "小数桁", "medium", "length"),
        Attr("nullable", "NULL", "high", "nullable"),
        Attr("default", "初期値", "medium"),
        Attr("pk", "PK", "high", "bool"),
        Attr("fk", "FK", "high", "fk"),
        Attr("indexed", "INDEX", "low", "bool"),
        Attr("identity", "自動採番", "low", "bool"),
        Attr("case_insensitive", "大小区別", "medium", "ci"),
        Attr("unsigned", "符号なし", "low", "bool"),
        Attr("description", "説明", "low"),
        Attr("title", "論理名", "low", scope="container"),
        Attr("summary", "説明", "low", scope="container"),
        Attr("kind", "種別", "low", scope="container"),
        Attr("volume", "想定件数", "low", scope="container"),
        Attr("unique", "一意制約", "low", "text", scope="container"),
        Attr("indexes", "複合インデックス", "low", "text", scope="container"),
    ]},
)


def extract(src, cfg, project):
    full = os.path.join(project, cfg["path"])
    kind = cfg["kind"]
    if kind == "ddl":
        ddl.extract(src, fio.read(full), cfg.get("dialect"), cfg.get("comment_as", "logical_name"))
    elif kind == "md":
        md.extract(src, fio.read(full), cfg.get("dialect"))
    elif kind == "xlsx":
        xlsx.extract(src, full, cfg["sheet"], cfg.get("dialect"))
    elif kind == "jpa":
        jpa.extract(src, full, project)
    else:
        raise ValueError(f"テーブル定義で未対応の情報源の種類: {kind}")
