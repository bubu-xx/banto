"""banto — 成果物の関係をMDの台帳で管理し、ずれを判断票にする。

使い方（対象プロジェクトのフォルダで実行するか、--project で指定する）:
  banto init                      案件の設定（project.json）と情報源の一覧のひな形を作る
  banto sync                      情報源を読み、台帳・判断票・一覧・網羅表を更新する
  banto status                    ずれの件数を表示する
  banto decide DRF-0001 --set 20 --by 名前 --reason 理由
  banto decide --group "<グループ>" --allow --by 名前 --reason 理由
  banto decide DRF-0050 --accept|--reject|--answer --by 名前 --reason 内容   （レビュー指摘）
  banto coverage                  網羅表を更新する（様式の各項目が、充足・情報不足・不要の候補か）
  banto decide --item BD-07 --exclude|--include --by 名前 --reason 理由   （様式の項目の要・不要）
  banto check [--strict]          IDの鎖と記録の整合を検査する（--strict は未判断・直し待ちも失敗にする）
  banto export [--doc TD] [--out DIR]  様式どおりのExcel（基本設計書・詳細設計書・テーブル定義書・テスト仕様書）と空のレビュー表を出す
  banto release TD --by 承認者 --reason 理由 [--allow-open]   文書の版を提出版として確定する
  banto import-review FILE.xlsx   記入済みのレビュー表を取り込み、指摘を判断票にする
  banto format read 様式.xlsx --name 顧客様式   専用様式の構造を読み、配置の下書きを作る（以後 trial / confirm / map）
"""
import argparse
import os
import sys


def _root(a):
    return os.path.abspath(a.project or os.environ.get("BANTO_PROJECT") or os.getcwd())


def _project(a):
    p = _root(a)
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


def cmd_init(a):
    import json
    from . import project as PJ, fio
    root = _root(a)
    base = os.path.join(root, "banto")
    made = []
    if not os.path.exists(PJ.path(base)):
        cfg = json.loads(json.dumps(PJ.DEFAULT))
        cfg.update(system=a.system or os.path.basename(root), project=a.name or "", customer=a.customer or "")
        if a.judge or a.approver:
            people = {}
            for n in a.judge or []:
                people.setdefault(n, set()).add("judge")
            for n in a.approver or []:
                people.setdefault(n, set()).add("approver")
            cfg["people"] = [{"name": n, "roles": sorted(r)} for n, r in people.items()]
        PJ.save(base, cfg)
        made.append("banto/project.json")
    src = os.path.join(base, "sources.json")
    if not os.path.exists(src):
        fio.write(src, json.dumps({"domains": {"tables": [], "tests": []}}, ensure_ascii=False, indent=2) + "\n")
        made.append("banto/sources.json")
    print("作成しました: " + "、".join(made) if made else "すでに準備済みです（既存のファイルは変更していません）")
    print("次に: sources.json に情報源を書き、banto sync を実行してください")
    return 0


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
    if a.item:
        return _decide_item(a, project, base, st)
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
    from . import project as PJ
    err = PJ.check_role(PJ.load(base), a.by, "judge")
    if err:
        sys.exit(err)
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


def _decide_item(a, project, base, st):
    """様式の項目が、このシステムに必要か不要かの判断を記録する。"""
    from . import engine, decisions as D, formats, project as PJ
    if bool(a.exclude) == bool(a.include):
        sys.exit("--item には --exclude（不要）か --include（必要）のどちらか一方を指定してください")
    if not a.by or not a.reason:
        sys.exit("--by（判断した人）と --reason（理由）は必須です")
    cfg = PJ.load(base)
    err = PJ.check_role(cfg, a.by, "judge")
    if err:
        sys.exit(err)
    known = formats.item_ids(formats.load(base, cfg.get("format", "standard")))
    if a.item not in known:
        sys.exit(f"{a.item} は様式の項目にない（banto/coverage/README.md を参照）")
    existing = [f[:-3] for f in os.listdir(os.path.join(base, "decisions"))] if os.path.isdir(os.path.join(base, "decisions")) else []
    action = "exclude" if a.exclude else "include"
    dec = D.Decision(st.dec_id([x for x in existing if x.startswith("DEC-")]), [], action, "", a.item, "", a.rule or "",
                     a.by, "", a.reason)
    doc, it = known[a.item]
    D.write(base, dec, f"対象：{doc['title']} {a.item} {it['title']}（{'不要' if a.exclude else '必要'}）")
    print(f"{dec.id} を記録しました：{a.item} {it['title']} を{'不要' if a.exclude else '必要'}と判断")
    res = engine.sync(project)
    c = next((c for c in res.coverage if c.id == a.item), None)
    if c:
        print(f"  {a.item}: {c.applicability}・{c.sufficiency}")
    return 0


def cmd_coverage(a):
    from . import engine
    res = engine.sync(_project(a))
    for e in res.errors:
        print(f"[誤り] {e}", file=sys.stderr)
    from collections import Counter
    n = Counter("不要" if not c.needed else c.sufficiency for c in res.coverage)
    cand = sum(1 for c in res.coverage if c.applicability == "不要の候補")
    print(f"網羅表を更新しました（banto/coverage/README.md）：充足 {n['充足']}・情報不足 {n['情報不足']}・"
          f"参照 {n['参照']}・不要の候補 {cand}・不要（判断済み） {n['不要'] - cand}")
    for c in res.coverage:
        if c.applicability == "不要の候補" or (c.needed and c.sufficiency == "情報不足"):
            what = c.applicability if c.applicability == "不要の候補" else "、".join(c.details)
            print(f"  {c.id} {c.item['title']}: {what}")
    return 0


def cmd_check(a):
    from . import check
    return check.run(_project(a), strict=a.strict)


def cmd_export(a):
    from . import excel
    project = _project(a)
    for p in excel.export(project, a.out, a.doc):
        print(f"出力: {os.path.relpath(p, project)}")
    return 0


def cmd_release(a):
    from . import release
    if not a.by or not a.reason:
        sys.exit("--by（承認者）と --reason（承認の理由・条件）は必須です")
    code, msg = release.run(_project(a), a.doc, a.by, a.reason, a.allow_open)
    print(msg, file=sys.stderr if code else sys.stdout)
    return code


def cmd_format(a):
    from . import custom, engine, project as PJ
    root = _root(a)
    base = os.path.join(root, "banto")
    if a.action == "read":
        if not a.file:
            sys.exit("様式のExcelファイルを指定してください：banto format read <様式.xlsx> --name <名前>")
        lay = custom.read(base, a.file, a.name)
        d = os.path.relpath(custom.fdir(base, a.name), root)
        print(f"読み取りました：{d}/STRUCTURE.md（構造）、{d}/layout.json（配置の下書き）")
        for s in lay["sheets"]:
            print(f"  シート「{s['sheet']}」：役割 {s['role']}、欄 {len(s['fields'])}、表 {len(s['tables'])}")
        for q in lay["questions"]:
            print(f"  確認したいこと：{q}")
        print("次に：banto format trial で試し刷りを作り、配置を確かめてください")
    elif a.action == "trial":
        res = engine.sync(_project(a)) if a.data else None
        p = custom.trial(base, a.name, a.data, res)
        print(f"試し刷り：{os.path.relpath(p, root)}")
    elif a.action == "map":
        doc = {"id": a.doc_id or "CX", "title": a.doc_title or a.name}
        mp = custom.map_draft(base, a.name, doc)
        print(f"対応づけの下書き：{os.path.relpath(os.path.join(custom.fdir(base, a.name), 'mapping.json'), root)}")
        for u in mp["unmapped"]:
            print(f"  要確認：{u}")
    elif a.action == "confirm":
        if not a.by:
            sys.exit("--by（確かめた人）は必須です")
        custom.confirm(base, a.name, a.step, a.by)
        print(f"{a.step} を確定しました（{a.by}）")
        if a.step == "mapping":
            cfg = PJ.load(base)
            print(f"この様式で出力するには project.json の format を \"custom:{a.name}\" にしてください（いま：{cfg.get('format')}）")
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
    s = sp.add_parser("init", help="案件の設定と情報源の一覧のひな形を作る")
    s.add_argument("--system")
    s.add_argument("--name")
    s.add_argument("--customer")
    s.add_argument("--judge", action="append")
    s.add_argument("--approver", action="append")
    s.set_defaults(func=cmd_init)
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
    s.add_argument("--item", help="様式の項目ID（--exclude / --include と使う）")
    s.add_argument("--exclude", action="store_true")
    s.add_argument("--include", action="store_true")
    s.set_defaults(func=cmd_decide)
    s = sp.add_parser("coverage", help="網羅表（設計書を作る情報が揃っているか）を更新して表示する")
    s.add_argument("path", nargs="?")
    s.set_defaults(func=cmd_coverage)
    s = sp.add_parser("check")
    s.add_argument("--strict", action="store_true")
    s.set_defaults(func=cmd_check)
    s = sp.add_parser("export")
    s.add_argument("--out")
    s.add_argument("--doc", action="append", help="出力する文書のID（BD・DD・TD・TS など。省略時はすべて）")
    s.set_defaults(func=cmd_export)
    s = sp.add_parser("release", help="文書の版を提出版として確定する（承認者）")
    s.add_argument("doc")
    s.add_argument("--by")
    s.add_argument("--reason")
    s.add_argument("--allow-open", action="store_true")
    s.set_defaults(func=cmd_release)
    s = sp.add_parser("format", help="専用様式の取り込み（read → trial → confirm layout → map → confirm mapping）")
    s.add_argument("action", choices=["read", "trial", "map", "confirm"])
    s.add_argument("file", nargs="?")
    s.add_argument("--name", required=True)
    s.add_argument("--data", action="store_true", help="trial：実際の値を入れて試し刷りする（対応づけの確認用）")
    s.add_argument("--step", choices=["layout", "mapping"], default="layout")
    s.add_argument("--by")
    s.add_argument("--doc-id")
    s.add_argument("--doc-title")
    s.set_defaults(func=cmd_format)
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
