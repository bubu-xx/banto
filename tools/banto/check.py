"""整合の検査（banto check）。ファイルは書き換えない。

検査すること:
  - 判断の記録（DEC）の書き方の誤り、存在しないずれへの参照
  - 台帳のIDと採番表の食い違い、IDの重複
  - テストの「対象」に書かれたIDが台帳に存在するか（IDの鎖）
  - 判断票の target が台帳に存在するか
--strict のときは、未判断・直し待ちが残っていても失敗にする（CIで使う）。
"""
import os
import re
from collections import Counter
from . import engine, fio, frontmatter, ledger as LG
from .domains import get

ID_RE = re.compile(r"\b(?:TBL|COL|TSU|TC)-\d+\b")


def run(project, strict=False):
    res = engine.sync(project, write=False)
    errors, warns, infos = list(res.errors), [], []
    st = res.state
    by_id = st.by_drift_id()
    for dec in res.decisions:
        for did in dec.drifts:
            if did not in by_id:
                errors.append(f"{dec.id}: 存在しないずれ {did} を参照している")
        if not dec.decided_by:
            warns.append(f"{dec.id}: 判断した人（decided_by）が空")
        if not dec.reason or dec.reason == "（記載なし）":
            warns.append(f"{dec.id}: 理由が空")

    all_ids = Counter()
    targets = st.by_target_id()
    for dname, ledger in res.ledgers.items():
        dom = get(dname)
        on_disk = LG.load_all(res.base, dom)
        for name, lc in on_disk.items():
            all_ids[lc.id] += 1
            want = st.ids["containers"].get(f"{dname}|{name}")
            if want and want != lc.id:
                errors.append(f"台帳 {name}: IDが {lc.id} だが採番表では {want}")
            for iname, it in lc.items.items():
                all_ids[it.id] += 1
                want = st.ids["items"].get(f"{dname}|{name}|{iname}")
                if want and want != it.id:
                    errors.append(f"台帳 {name}.{iname}: IDが {it.id} だが採番表では {want}")
                for fc, text in it.free.items():
                    for ref in ID_RE.findall(text or ""):
                        if ref not in targets:
                            errors.append(f"台帳 {name}.{iname} の「{fc}」: {ref} は台帳にない（IDの鎖が切れている）")
    for i, n in all_ids.items():
        if n > 1 and i:
            errors.append(f"ID {i} が台帳の中で {n} 回使われている")

    ddir = os.path.join(res.base, "drifts")
    if os.path.isdir(ddir):
        for f in sorted(os.listdir(ddir)):
            if f.startswith("DRF-"):
                meta, _ = frontmatter.load(fio.read(os.path.join(ddir, f)))
                t = meta.get("target")
                if t and meta.get("domain") != "review" and t not in targets:
                    warns.append(f"{f[:-3]}: target {t} が台帳にない")

    # IDの鎖：テストの「対象」で、どの列がどのテストで確認されているか
    linked = set()
    for lc in res.ledgers.get("tests", {}).values():
        for it in lc.items.values():
            linked |= set(ID_RE.findall(it.free.get("対象", "") or ""))
    cols = [it.id for lc in res.ledgers.get("tables", {}).values() for it in lc.items.values()]
    if cols and "tests" in res.ledgers:
        covered = [c for c in cols if c in linked]
        infos.append(f"テストの「対象」から辿れる列：{len(covered)} / {len(cols)}")

    op = [d for d in res.drifts if d.status == "open"]
    dc = [d for d in res.drifts if d.status == "decided"]
    infos.append(f"未判断 {len(op)} 件・直し待ち {len(dc)} 件")
    for e in errors:
        print(f"[誤り] {e}")
    for w in warns:
        print(f"[注意] {w}")
    for i in infos:
        print(f"[情報] {i}")
    if errors:
        return 1
    if strict and (op or dc):
        print("[失敗] --strict: 未判断または直し待ちのずれが残っている")
        return 1
    print("OK")
    return 0
