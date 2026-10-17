"""提出（banto release）：文書の版を確定し、承認者・残っている課題・前回提出版からの変更を記録する。

提出した版のExcelと中身の写しは banto/releases/<文書ID>-v<版>/ に残る。以後に台帳が変われば次の版になり、
改訂履歴と提出記録に「前回提出版からの変更」が出る。
未判断のずれ・情報不足・不要の候補が残っているときは、--allow-open（理由つき）を付けない限り提出しない。
"""
import datetime
import json
import os
import shutil
from . import excel, fio, project as PJ


def run(project, doc_id, by, reason, allow_open=False):
    base = os.path.join(project, "banto")
    cfg = PJ.load(base)
    err = PJ.check_role(cfg, by, "approver")
    if err:
        return 1, err
    files = excel.export(project, only=[doc_id])
    from . import engine
    res = engine.sync(project, write=False)
    fmt = res.format
    doc = next((d for d in fmt["documents"] if d["id"] == doc_id), None)
    if doc is None:
        return 1, f"{doc_id} は様式の文書にない（{'、'.join(d['id'] for d in fmt['documents'])}）"
    data = excel.load_versions(base)
    v = data[doc_id]
    if any(r["version"] == v["version"] for r in v.get("released", [])):
        return 1, f"{doc['title']} 第{v['version']}版はすでに提出済み。台帳を変えてから出し直すと次の版になる"
    covs = {c.id: c for c in res.coverage}
    domains = {it["domain"] for it in doc["items"] if it.get("domain")}
    open_drifts = [d for d in res.drifts if d.domain is not None and d.domain.name in domains and d.status == "open"]
    decided = [d for d in res.drifts if d.domain is not None and d.domain.name in domains and d.status == "decided"]
    lacking = [covs[it["id"]] for it in doc["items"] if it["id"] in covs and covs[it["id"]].needed
               and covs[it["id"]].sufficiency == "情報不足"]
    cands = [covs[it["id"]] for it in doc["items"] if it["id"] in covs and covs[it["id"]].applicability == "不要の候補"]
    issues = ([f"未判断のずれ {len(open_drifts)}件"] if open_drifts else []) + \
             ([f"直し待ち {len(decided)}件"] if decided else []) + \
             ([f"情報不足 {len(lacking)}項目（" + "、".join(c.id for c in lacking) + "）"] if lacking else []) + \
             ([f"要・不要が未判断 {len(cands)}項目（" + "、".join(c.id for c in cands) + "）"] if cands else [])
    if issues and not allow_open:
        return 1, ("提出できない：" + "、".join(issues) +
                   "。このまま提出するなら --allow-open を付け、理由を --reason に書く（提出記録に残る）")
    prev = v.get("released", [])[-1] if v.get("released") else None
    rdir = os.path.join(base, "releases", f"{doc_id}-v{v['version']}")
    os.makedirs(rdir, exist_ok=True)
    book = next((f for f in files if os.path.basename(f).startswith(f"{doc_id}_")), None)
    if book is None:
        return 1, f"{doc_id} のExcelが出力されていない"
    shutil.copy2(book, os.path.join(rdir, os.path.basename(book)))
    snap = v["snapshot"]
    fio.write(os.path.join(rdir, "snapshot.json"), json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    if prev:
        old = json.loads(fio.read(os.path.join(base, "releases", f"{doc_id}-v{prev['version']}", "snapshot.json")))
        changes, n = excel._diff(old, snap, limit=200)
    else:
        changes, n = [], 0
    today = datetime.date.today().isoformat()
    by_drift = res.state.by_drift_id()
    item_ids = {it["id"] for it in doc["items"]}

    def relevant(d):
        if d.target in item_ids:
            return True
        return any(by_drift.get(x, "").split("|", 1)[0] in domains for x in d.drifts)

    since = [d for d in res.decisions if relevant(d)
             and d.id in set(res.state.applied) - set(prev.get("decisions", []) if prev else [])]
    L = [f"# 提出記録 {doc['title']} 第{v['version']}版", "",
         f"- 文書：{doc_id} {doc['title']}", f"- 版：第{v['version']}版", f"- 提出日：{today}", f"- 承認者：{by}",
         f"- 承認の理由・条件：{reason}", f"- Excel：{os.path.basename(book)}", ""]
    L += ["## 前回提出版からの変更", ""]
    if prev:
        L += [f"前回：第{prev['version']}版（{prev['date']}、承認 {prev['by']}）。変更 {n} 件。", ""] + [f"- {c}" for c in changes]
    else:
        L.append("初回の提出。")
    L += ["", "## この版までに反映した判断", ""]
    L += [f"- {d.id}（{d.decided_by}、{d.decided_at}）：{d.reason.splitlines()[0] if d.reason else ''}" for d in since] or ["- なし"]
    L += ["", "## 残っている課題（承認者が了承して提出）", ""]
    L += [f"- {x}" for x in issues] or ["- なし"]
    fio.write(os.path.join(rdir, "RELEASE.md"), "\n".join(L) + "\n")
    v.setdefault("released", []).append({"version": v["version"], "date": today, "by": by, "reason": reason,
                                         "decisions": sorted(res.state.applied), "open": issues})
    excel.save_versions(base, data)
    excel.export(project, only=[doc_id])  # 表紙と改訂履歴に承認を載せ直す（中身は同じなので版は変わらない）
    shutil.copy2(book, os.path.join(rdir, os.path.basename(book)))
    return 0, f"{doc['title']} 第{v['version']}版を提出版として確定しました（{os.path.relpath(rdir, project)}）"
