"""領域: テスト（コンテナ = テストクラス、項目 = テストメソッド）"""
import os
from .base import Attr, Domain
from .. import fio
from ..extract import mdtests, junit, surefire

DOMAIN = Domain(
    name="tests", title="テスト仕様書", container_label="テストクラス", item_label="テスト",
    container_prefix="TSU", item_prefix="TC", ledger_dir="tests", exists_severity="medium",
    attrs={a.name: a for a in [
        Attr("category", "種別", "low"),
        Attr("purpose", "検証内容", "low"),
        Attr("precondition", "前提条件", "low"),
        Attr("steps", "手順", "low"),
        Attr("expected", "期待結果", "low"),
        Attr("result", "結果", "high", authority="surefire", choices=("pass", "fail", "error", "skipped")),
        Attr("level", "テストレベル", "low", scope="container"),
        Attr("summary", "目的", "low", scope="container"),
    ]},
    free_columns=("対象",),
)


def extract(src, cfg, project):
    full = os.path.join(project, cfg["path"])
    kind = cfg["kind"]
    if kind == "md":
        mdtests.extract(src, fio.read(full), cfg.get("columns", {}), cfg.get("sections", {}))
    elif kind == "junit":
        junit.extract(src, full, project)
    elif kind == "surefire":
        src.existence = False
        surefire.extract(src, full, project)
    else:
        raise ValueError(f"テストで未対応の情報源の種類: {kind}")
