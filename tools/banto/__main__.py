"""使い方: python -m banto import-tables <対象プロジェクトのパス>

<対象>/banto/sources.json に書かれた情報源からテーブル定義を取り出し、突き合わせて、
  banto/extracted/tables.json      取り出した事実（再現・比較用）
  banto/design/detail/tables/*.md  テーブル定義（一致した部分と、未判断のずれへの参照）
  banto/drifts/DRF-*.md            判断票
  banto/drifts/README.md           ずれの一覧（グループ別）
を書き出す。どれが正かは決めない。
"""
import json
import os
import sys
from . import sources as S, match, render


def import_tables(project):
    srcs = S.load(project)
    base = os.path.join(project, "banto")
    for sub in ("extracted", "design/detail/tables", "drifts", "decisions"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    json.dump(S.dump(srcs), open(os.path.join(base, "extracted", "tables.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=list)
    drifts, agreed, attr_name = match.compare(srcs)
    tables = sorted({t for s in srcs for t in s.tables})
    tbl_ids = {t: f"TBL-{i:03d}" for i, t in enumerate(tables, 1)}
    col_ids, n = {}, 0
    for t in tables:
        seen = []
        for s in srcs:
            for c in s.tables.get(t, type("x", (), {"columns": {}})).columns:
                if c not in seen:
                    seen.append(c)
        for c in seen:
            n += 1
            col_ids[(t, c)] = f"COL-{n:03d}"
    outdir = os.path.join(base, "drifts")
    for d in drifts:
        render.write_drift(project, outdir, d, srcs, attr_name, col_ids, tbl_ids)
    render.write_index(outdir, drifts, attr_name)
    render.write_tables(project, os.path.join(base, "design", "detail", "tables"), srcs, drifts, agreed, col_ids, tbl_ids)
    return srcs, drifts, tables


def main(argv):
    if len(argv) != 2 or argv[0] != "import-tables":
        print(__doc__)
        return 2
    srcs, drifts, tables = import_tables(argv[1])
    print(f"情報源 {len(srcs)} 件、テーブル {len(tables)} 件、ずれ {len(drifts)} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
