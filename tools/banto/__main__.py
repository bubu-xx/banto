"""banto — 成果物の関係をMDの台帳で管理し、ずれを判断票にする。

使い方（対象プロジェクトのフォルダで実行するか、--project で指定する）:
  banto sync                      情報源を読み、台帳・判断票・一覧を更新する
  banto status                    ずれの件数を表示する
  banto decide DRF-0001 --set 20 --by 名前 --reason 理由
  banto decide --group "<グループ>" --allow --by 名前 --reason 理由
  banto decide DRF-0050 --accept|--reject|--answer --by 名前 --reason 内容   （レビュー指摘）
  banto check [--strict]          IDの鎖と記録の整合を検査する（--strict は未判断・直し待ちも失敗にする）
  banto export [--out DIR]        台帳からExcel（設計書・テスト仕様書）と空のレビュー表を出す
  banto import-review FILE.xlsx   記入済みのレビュー表を取り込み、指摘を判断票にする
"""
import argparse
import os
import sys


def _project(a):
    p = os.path.abspath(a.project or os.environ.get("BANTO_PROJECT") or os.getcwd())
    if not os.path.exists(os.path.join(p, "banto", "sources.json")):
        sys.exit(f"banto/sources.json が見つからない: {p}\n対象プロジェクトのフォルダで実行するか、--project で指定してください。")
    return p


def _summary(res):
    from collections import Counter
    out = []
    by = Counter((d.domain.title if d.domain else "レビュー", d.status) for d in res.drifts)
    for dom in sorted({k[0] for k in by}):
        out.append(f"  {dom}: 未判断 {by[(dom, 'open')]}・直し待ち {by[(dom, 'decided')]}・解決済み {by[(dom, 'resolved')]}")
    return "\n".join(out) or "  ずれなし"


def cmd_sync(a):
    from . import engine
    res = engine.sync(_project(a))
    n = {d: sum(len(c.items) for c in l.values()) for d, l in res.ledgers.items()}
    print("同期しました（" + "、".join(f"{d} {len(l)}件／項目 {n[d]}件" for d, l in res.ledgers.items()) + "）")
    print(_summary(res))
    for e in res.errors:
        print(f"[判断の記録の誤り] {e}", file=sys.stderr)
    return 1 if res.errors else 0


def cmd_status(a):
    from . import engine
    res = engine.sync(_project(a), write=False)
    print(_summary(res))
    return 0


def cmd_decide(a):
    from . import engine, decisions as D
    from .state import State, split
    from .domains import get
    project = _project(a)
    base = os.path.join(project, "banto")
    st = State(base)
    reg = st.drifts
    by_id = st.by_drift_id()
    ids = list(a.drifts)
    if a.group:
        ids += [e["id"] for k, e in sorted(reg.items(), key=lambda kv: kv[1]["id"])
                if e.get("group") == a.group and e["status"] == "open" and e["id"] not in ids]
        if not ids:
            sys.exit(f"グループ「{a.group}」に未判断のずれがない")
    if not ids:
        sys.exit("対象のずれ（DRF-xxxx）か --group を指定してください")
    flags = [n for n in ("accept", "reject", "answer", "allow") if getattr(a, n)] + (["set"] if a.set is not None and not a.accept else [])
    if len(flags) > 1:
        sys.exit("--set / --allow / --accept / --reject / --answer は1つだけ指定してください")
    action = flags[0] if flags else None
    if not action:
        sys.exit("--set / --allow / --accept / --reject / --answer のどれかを指定してください")
    if not a.by or not a.reason:
        sys.exit("--by（判断した人）と --reason（理由）は必須です。理由は次の判断の材料になります")
    value = a.set if action == "set" else (a.value or "")
    for did in ids:
        k = by_id.get(did)
        if not k:
            sys.exit(f"{did} は登録されていない（banto sync を先に実行してください）")
        dname, c, i, attr = split(k)
        if action in ("set", "allow"):
            if dname == "review":
                sys.exit(f"{did} はレビュー指摘です。--accept / --reject / --answer を使ってください")
            if value:
                try:
                    get(dname).attr(attr).parse(value)
                except ValueError as e:
                    sys.exit(f"{did}: {e}")
        elif dname != "review":
            sys.exit(f"{did} はレビュー指摘ではありません。--set か --allow を使ってください")
        if reg[k]["status"] != "open":
            print(f"注意: {did} は「{reg[k]['status']}」の状態です（判断を上書きします）", file=sys.stderr)
    if action == "accept" and (a.target or a.attr or a.value or a.set):
        a.value = a.value or a.set
        if not (a.target and a.attr and a.value):
            sys.exit("台帳を直すときは --target と --attr と --set（値）をそろえて指定してください")
        t = st.by_target_id().get(a.target)
        if not t:
            sys.exit(f"{a.target} は台帳にない")
        try:
            get(t[0]).attr(a.attr).parse(a.value)
        except (ValueError, KeyError) as e:
            sys.exit(f"--attr / --value が不正: {e}")
        value = a.value
    existing = [f[:-3] for f in os.listdir(os.path.join(base, "decisions"))] if os.path.isdir(os.path.join(base, "decisions")) else []
    dec = D.Decision(st.dec_id([x for x in existing if x.startswith("DEC-")]), ids, action, value,
                     a.target or "", a.attr or "", a.rule or (f"グループ {a.group}" if a.group else ""),
                     a.by, "", a.reason)
    summary = f"対象：{'、'.join(ids)}"
    p = D.write(base, dec, summary)
    print(f"{dec.id} を記録しました: {os.path.relpath(p, project)}")
    res = engine.sync(project)
    for e in res.errors:
        print(f"[判断の記録の誤り] {e}", file=sys.stderr)
    by_new = {d.id: d for d in res.drifts}
    for did in ids:
        d = by_new.get(did)
        if d:
            rest = f"（直し待ち: {', '.join(d.deviating)}）" if d.status == "decided" else ""
            print(f"  {did}: {d.status}{rest}")
    return 1 if res.errors else 0


def cmd_check(a):
    from . import check
    return check.run(_project(a), strict=a.strict)


def cmd_export(a):
    from . import excel
    project = _project(a)
    for p in excel.export(project, a.out):
        print(f"出力: {os.path.relpath(p, project)}")
    return 0


def cmd_import_review(a):
    from . import review_io, engine
    project = _project(a)
    n, warns = review_io.import_file(project, a.file)
    for w in warns:
        print(f"注意: {w}", file=sys.stderr)
    print(f"指摘 {n} 件を取り込みました")
    res = engine.sync(project)
    print(_summary(res))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="banto", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", help="対象プロジェクトのフォルダ（既定: カレント、または環境変数 BANTO_PROJECT）")
    sp = p.add_subparsers(dest="cmd")
    for name in ("sync", "import-tables"):
        s = sp.add_parser(name, help="台帳・判断票を更新する")
        s.add_argument("path", nargs="?")
        s.set_defaults(func=cmd_sync)
    s = sp.add_parser("status")
    s.add_argument("path", nargs="?")
    s.set_defaults(func=cmd_status)
    s = sp.add_parser("decide", help="判断を記録する")
    s.add_argument("drifts", nargs="*")
    s.add_argument("--group")
    s.add_argument("--set")
    s.add_argument("--allow", action="store_true")
    s.add_argument("--value")
    s.add_argument("--accept", action="store_true")
    s.add_argument("--reject", action="store_true")
    s.add_argument("--answer", action="store_true")
    s.add_argument("--target")
    s.add_argument("--attr")
    s.add_argument("--by")
    s.add_argument("--reason")
    s.add_argument("--rule")
    s.set_defaults(func=cmd_decide)
    s = sp.add_parser("check")
    s.add_argument("--strict", action="store_true")
    s.set_defaults(func=cmd_check)
    s = sp.add_parser("export")
    s.add_argument("--out")
    s.set_defaults(func=cmd_export)
    s = sp.add_parser("import-review")
    s.add_argument("file")
    s.set_defaults(func=cmd_import_review)
    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help()
        return 2
    if getattr(a, "path", None):
        a.project = a.path
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
