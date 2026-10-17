"""突合せの結果を、テーブル定義のMD・判断票・一覧に書き出す。"""
import os
import re
import subprocess
from .extract.sqltype import show_length

SEV_JA = {"high": "高", "medium": "中", "low": "低"}


def _val(attr, v):
    if attr == "length":
        return "—" if v is None else show_length(v)
    if attr in ("nullable",):
        return "NULL許容" if v else "必須（NOT NULL相当）"
    if attr == "exists":
        return "あり" if v else "記載なし"
    if attr == "case_insensitive":
        return "区別しない" if v else "区別する"
    if isinstance(v, bool):
        return "○" if v else "×"
    if isinstance(v, tuple):
        return "、".join("(" + ", ".join(k) + ")" for k in v) or "なし"
    return str(v)


def _camel(col):
    p = col.split("_")
    return p[0] + "".join(x.title() for x in p[1:])


def _tests(project, col):
    """テストコードで列名・フィールド名に触れている箇所（下流の手がかり）。"""
    hits, root = [], os.path.join(project, "src", "test")
    if not col or not os.path.isdir(root):
        return hits
    pat = re.compile(r"\b(" + re.escape(col) + "|" + re.escape(_camel(col)) + r")\b")
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            n = [i + 1 for i, ln in enumerate(open(p, encoding="utf-8", errors="ignore")) if pat.search(ln)]
            if n:
                hits.append((os.path.relpath(p, project).replace(os.sep, "/"), n))
    return sorted(hits)


def _notes(project, sources, table, col):
    """MD設計書の箇条書きで、この項目に触れている記載（経緯・注意点の手がかり）。"""
    out = []
    key = col or table
    for s in sources:
        if s.kind != "md":
            continue
        for i, ln in enumerate(open(os.path.join(project, s.path), encoding="utf-8").read().splitlines(), 1):
            if ln.lstrip().startswith(("- ", "* ")) and re.search(r"\b" + re.escape(key) + r"\b", ln):
                out.append((f"{s.path}:{i}", ln.strip()[2:]))
    return out[:5]


def _history(project, paths):
    try:
        out = subprocess.run(["git", "-C", project, "log", "--date=short", "--format=%h %ad %s", "-n", "3", "--", *paths],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        out = ""
    return out.splitlines()


def write_drift(project, outdir, d, sources, attr_name, col_ids, tbl_ids):
    target = col_ids.get((d.table, d.column)) or tbl_ids.get(d.table)
    where = f"{d.table}.{d.column}" if d.column else d.table
    L = ["---", f"id: {d.id}", f"kind: {d.kind}", f"targets: [{target}]", f"attribute: {d.attr}",
         f"severity: {d.severity}", f"group: \"{d.group}\"", "status: open", "---", "",
         f"# {d.id} {where} の{attr_name[d.attr]}", "", f"グループ：{d.group_label}", "",
         "## 何がずれているか", "", "| 情報源 | 値 | 書かれ方 | 場所 |", "|---|---|---|---|"]
    for s, v, shown, loc in d.values:
        L.append(f"| {s.label} | {_val(d.attr, v)} | {shown} | `{loc}` |")
    silent = [s for s in sources if s.id not in {x.id for x, *_ in d.values}]
    if silent and d.attr != "exists":
        L += ["", "この属性を表していない情報源（比較対象外）：" + "、".join(s.label for s in silent)]

    L += ["", "## つながり", ""]
    up = [(s, loc) for s, v, _, loc in d.values if s.kind in ("md", "xlsx")]
    down = [(s, loc) for s, v, _, loc in d.values if s.kind not in ("md", "xlsx")]
    L.append("- 上流（設計書）：" + ("、".join(f"{s.label} `{loc}`" for s, loc in up) or "なし"))
    L.append("- 実物：" + ("、".join(f"{s.label} `{loc}`" for s, loc in down) or "なし"))
    tests = _tests(project, d.column)
    if tests:
        L.append("- 下流（テストで触れている箇所）：")
        for p, ns in tests[:6]:
            L.append(f"  - `{p}` 行 {', '.join(map(str, ns[:8]))}{' …' if len(ns) > 8 else ''}")
    else:
        L.append("- 下流（テスト）：該当なし")

    L += ["", "## 経緯", ""]
    notes = _notes(project, sources, d.table, d.column)
    for loc, text in notes:
        L.append(f"- 設計書の記載 `{loc}`：{text}")
    hist = _history(project, sorted({s.path for s, *_ in d.values}))
    if hist:
        L.append("- 変更履歴：" + " ／ ".join(hist))
        if len(hist) == 1:
            L.append("  - この時点の履歴は基準コミットのみで、いつ・なぜ食い違ったかは記録から辿れない")
    for s in sources:
        if s.scope_note and d.attr == "exists" and any(x.id == s.id and not v for x, v, *_ in d.values):
            L.append(f"- {s.label} の対象範囲：{s.scope_note}")

    L += ["", "## 選択肢と影響", ""]
    if d.attr == "exists":
        lacking = [s.label for s, v, *_ in d.values if not v]
        having = [s.label for s, v, *_ in d.values if v]
        L.append(f"- A. 記載のない側に追加する → 変更が必要：{'、'.join(lacking)}")
        L.append(f"- B. 実物から取り除く（使われていない場合）→ 変更が必要：{'、'.join(having)}")
        L.append("- C. 対象範囲外として記録し、どれも変更しない（範囲外とする理由を残す）")
    else:
        distinct = []
        for s, v, *_ in d.values:
            if repr(v) not in [repr(x) for x in distinct]:
                distinct.append(v)
        for i, v in enumerate(distinct):
            others = [s.label for s, x, *_ in d.values if repr(x) != repr(v)]
            L.append(f"- {chr(65 + i)}. 「{_val(d.attr, v)}」を正とする → 変更が必要：{'、'.join(others)}")
        L.append(f"- {chr(65 + len(distinct))}. 意図した違い（DB方言の差、アプリと DB の役割分担など）として記録し、どれも変更しない")
    L += ["", "## 判断", "", "（未判断。判断したら decisions/ に DEC-xxxx を作り、ここに番号を書く）", ""]
    open(os.path.join(outdir, f"{d.id}.md"), "w", encoding="utf-8").write("\n".join(L))


def write_index(outdir, drifts, attr_name):
    from collections import Counter, OrderedDict
    sev = Counter(d.severity for d in drifts)
    L = ["# 未判断のずれ一覧", "",
         f"合計 {len(drifts)} 件（高 {sev['high']}・中 {sev['medium']}・低 {sev['low']}）。", "",
         "同じグループのずれは、同じ規則でまとめて判断できる候補。", ""]
    groups = OrderedDict()
    for d in drifts:
        groups.setdefault((d.severity, d.group_label), []).append(d)
    L += ["## グループ別", "", "| 重要度 | グループ | 件数 | 判断票 |", "|---|---|---|---|"]
    for (sv, gl), ds in groups.items():
        L.append(f"| {SEV_JA[sv]} | {gl} | {len(ds)} | " + " ".join(f"[{d.id}]({d.id}.md)" for d in ds) + " |")
    L += ["", "## 一覧", "", "| ID | 重要度 | 対象 | 属性 | 種類 |", "|---|---|---|---|---|"]
    for d in drifts:
        where = f"{d.table}.{d.column}" if d.column else d.table
        L.append(f"| [{d.id}]({d.id}.md) | {SEV_JA[d.severity]} | {where} | {attr_name[d.attr]} | {d.kind} |")
    open(os.path.join(outdir, "README.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def write_tables(project, outdir, sources, drifts, agreed, col_ids, tbl_ids):
    cols_order = {}
    for s in sources:
        for t in s.tables.values():
            for c in t.columns:
                cols_order.setdefault(t.name, [])
                if c not in cols_order[t.name]:
                    cols_order[t.name].append(c)
    by_cell = {}
    for d in drifts:
        by_cell.setdefault((d.table, d.column), {})[d.attr] = d.id
    shown_attrs = [("base_type", "型"), ("length", "長さ"), ("nullable", "NULL"), ("pk", "PK"),
                   ("fk", "FK"), ("indexed", "INDEX"), ("identity", "自動採番"), ("case_insensitive", "大小区別")]
    for tname in sorted(cols_order):
        tdr = [d for d in drifts if d.table == tname]
        status = "draft" if tdr else "confirmed"
        L = ["---", f"doc_id: {tbl_ids[tname]}", f"title: テーブル定義 {tname}", "kind: detail-design",
             "version: 0.1", f"status: {status}", "---", "", f"# {tname}", ""]
        if (tname, None) in by_cell:
            L += ["テーブル単位の未判断：" + "、".join(f"[{i}](../../../drifts/{i}.md)" for i in by_cell[(tname, None)].values()), ""]
        L += [f"未判断のずれ：{len(tdr)} 件", "",
              "| ID | 列 | " + " | ".join(n for _, n in shown_attrs) + " | 出どころ |",
              "|---|---|" + "---|" * len(shown_attrs) + "---|"]
        for cname in cols_order[tname]:
            cells, open_n = [], 0
            for a, _ in shown_attrs:
                did = by_cell.get((tname, cname), {}).get(a) or by_cell.get((tname, cname), {}).get("exists")
                if did:
                    cells.append(f"⚠ [{did}](../../../drifts/{did}.md)")
                    open_n += 1
                elif a in agreed.get((tname, cname), {}):
                    v, shown, n = agreed[(tname, cname)][a]
                    cells.append(_val(a, v) if a != "base_type" else str(v))
                else:
                    cells.append("—")
            origin = "未判断あり" if open_n else "extracted（情報源間で一致）"
            L.append(f"| {col_ids[(tname, cname)]} | `{cname}` | " + " | ".join(cells) + f" | {origin} |")
        L += ["", "○＝あり、×＝なし、「—」＝どの情報源も表していない属性。", "", "## 実物の場所", ""]
        for s in sources:
            t = s.tables.get(tname)
            L.append(f"- {s.label}：" + (f"`{t.loc}`" if t else "記載なし"))
        open(os.path.join(outdir, f"{tname}.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
