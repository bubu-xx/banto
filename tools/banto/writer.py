"""同期の結果を、台帳MD・判断票・一覧・直し待ちリストとして書き出す。

同じ入力からは必ず同じ出力になるよう、日時などの揺れる値は書かない（変更があったファイルだけ書き換える）。
"""
import os
import re
import subprocess
from collections import OrderedDict, Counter
from . import frontmatter, ledger as LG
from .state import split
from .domains import get as get_dom
from . import fio

SEV_JA = {"high": "高", "medium": "中", "low": "低"}
STATUS_JA = {"open": "未判断", "decided": "判断済み・直し待ち", "resolved": "解決済み"}
DOC_KINDS = ("md", "xlsx")


NOTES = "<!-- banto:notes -->"


def _keep_notes(path, text):
    """判断票の「補足」欄（人や照合係が書いた分析）は、同期で書き直しても残す。"""
    old = fio.read(path) if os.path.exists(path) else ""
    kept = old.split(NOTES, 1)[1].strip("\n") if NOTES in old else ""
    return text.rstrip("\n") + "\n\n## 補足\n\n人や照合係が書いた分析・意味の確認。この見出しより下は同期しても消えない。\n\n" + NOTES + "\n" + \
        (kept + "\n" if kept else "")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and fio.read(path) == text:
        return
    fio.write(path, text)


def _rel(frm_dir, to):
    return os.path.relpath(to, frm_dir).replace(os.sep, "/")


def write_all(res):
    _CACHE.clear()
    by_key = {d.key: d for d in res.drifts}
    paths = {s.path for ss in res.sources.values() for s in ss}
    paths |= {os.path.relpath(os.path.join(res.base, get_dom(dn).ledger_dir, LG.file_name(c)), res.project).replace(os.sep, "/")
              for dn, lg in res.ledgers.items() for c in lg}
    _git_index(res.project, paths)
    for dname, ledger in res.ledgers.items():
        write_ledger(res, dname, ledger, by_key)
    for d in res.drifts:
        write_drift(res, d)
    write_index(res)
    write_apply(res)


# ---------------------------------------------------------------- 台帳

def _target_id(res, d):
    if d.domain is None:
        return ""
    lc = res.ledgers[d.domain.name].get(d.container)
    if lc is None:
        return ""
    if d.item is None:
        return lc.id
    it = lc.items.get(d.item)
    return it.id if it else ""


def _marker(d, here):
    if d is None or d.status == "resolved":
        return ""
    sym = "⚠" if d.status == "open" else "⏳"
    return f" {sym}[{d.id}]({_rel(here, os.path.join(d._base, 'drifts', d.id + '.md'))})"


def write_ledger(res, dname, ledger, by_key):
    from .domains import get
    dom = get(dname)
    ddir = os.path.join(res.base, dom.ledger_dir)
    for d in res.drifts:
        d._base = res.base
    reg = res.state.drifts
    rows_index = []
    for name, lc in sorted(ledger.items(), key=lambda kv: kv[1].id):
        path = os.path.join(ddir, LG.file_name(name))
        keyf = lambda i, a: f"{dname}|{name}|{i or ''}|{a}"
        cont_drifts = [d for d in res.drifts if d.domain is dom and d.container == name and d.status != "resolved"]
        n_open = sum(1 for d in cont_drifts if d.status == "open")
        n_dec = sum(1 for d in cont_drifts if d.status == "decided")
        rows_index.append((lc, n_open, n_dec))
        meta = OrderedDict(doc_id=lc.id, title=f"{dom.container_label} {name}", domain=dname, container=name,
                           status=lc.status)
        L = [frontmatter.dump(meta), f"# {name}", ""]
        if lc.status == "pending":
            L += [f"この{dom.container_label}が台帳に載るべきかは未判断（情報源によって有無が違う）。", ""]
        if lc.status == "removed":
            L += ["このコンテナは、判断により取り除かれ、どの情報源にも無くなった。", ""]
        else:
            ce = by_key.get(keyf(None, "exists"))
            if ce and ce.status != "resolved":
                L += [f"{dom.container_label}の有無が未確定：{_marker(ce, ddir).strip()}", ""]
            L.append(f"未判断 {n_open} 件・直し待ち {n_dec} 件" if cont_drifts else "すべての情報源と一致している。")
            L.append("")
        cattrs = dom.container_attrs()
        if cattrs:
            L += ["<!-- banto:attrs -->", "| 属性 | 値 |", "|---|---|"]
            for a in cattrs:
                v = lc.attrs.get(a.name)
                L.append(f"| {a.label} | {a.show(v) if v is not None else '?'}{_marker(by_key.get(keyf(None, a.name)), ddir)} |")
            L.append("")
        iattrs = dom.item_attrs()
        head = ["ID", dom.item_label] + [a.label for a in iattrs] + list(dom.free_columns) + ["状態"]
        L += ["<!-- banto:items -->", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        for iname, it in lc.items.items():
            cells = [it.id, f"`{iname}`"]
            for a in iattrs:
                v = it.values.get(a.name)
                d = by_key.get(keyf(iname, a.name))
                txt = a.show(v) if v is not None else ("?" if d and d.status != "resolved" else a.show(None))
                cells.append(txt + _marker(d, ddir))
            for fc in dom.free_columns:
                cells.append(it.free.get(fc, ""))
            st = []
            ie = by_key.get(keyf(iname, "exists"))
            if it.exists is None:
                st.append("有無未定")
            elif not it.exists:
                st.append("削除予定")
            if ie and ie.status != "resolved":
                st.append(("有無が未判断" if ie.status == "open" else "有無の直し待ち") + _marker(ie, ddir))
            mine = [d for d in cont_drifts if d.item == iname and d.attr.name != "exists"]
            if any(d.status == "open" for d in mine):
                st.append("⚠ 未判断あり")
            if any(d.status == "decided" for d in mine):
                st.append("⏳ 直し待ちあり")
            if any(k.startswith(keyf(iname, "")) for k in lc.allowed):
                st.append("許容差あり")
            decs = sorted({e["decision"] for k, e in reg.items() if k.startswith(f"{dname}|{name}|{iname}|")
                           and e.get("decision")})
            if not st:
                st.append("✓ 一致" + (f"（{'、'.join(decs)}）" if decs else ""))
            cells.append(" ".join(st))
            L.append("| " + " | ".join(cells) + " |")
        L += ["", "? ＝未定（判断待ち）、— ＝どの情報源も表していない。⚠ ＝未判断、⏳ ＝判断済みで実物の直し待ち。", ""]
        L += ["<!-- banto:allowed -->", "## 許容された差", "",
              "判断により、台帳と違っていてよいと決めたもの。", "",
              "| 対象 | 属性 | 情報源 | 許容する値 | 判断 |", "|---|---|---|---|---|"]
        for k in sorted(lc.allowed):
            _, c, i, a = split(k)
            spec = dom.attr(a)
            tid = lc.items[i].id if i and i in lc.items else lc.id
            for sid, (v, dec) in sorted(lc.allowed[k].items()):
                L.append(f"| {tid} | {spec.label} | {sid} | {spec.show(v)} | {dec} |")
        L += ["", "## 実物の場所", ""]
        for s in res.sources.get(dname, []):
            sc = s.containers.get(name)
            L.append(f"- {s.label}（{s.id}）：" + (f"`{sc.loc}`" if sc else "なし"))
        L += ["", "## メモ", "", "<!-- banto:notes -->"]
        if lc.notes:
            L.append(lc.notes)
        _write(path, "\n".join(L).rstrip("\n") + "\n")
    # 領域の目次
    T = [f"# {dom.title}（台帳）", "",
         f"bantoの台帳。{dom.container_label}ごとに1ファイル。値を直接書き換えてもよい（次の同期で実物と照らし合わされる）。", "",
         f"| ID | {dom.container_label} | {dom.item_label}の数 | 状態 | 未判断 | 直し待ち |", "|---|---|---|---|---|---|"]
    for lc, no, nd in rows_index:
        T.append(f"| {lc.id} | [{lc.name}]({LG.file_name(lc.name)}) | {len(lc.items)} | {lc.status} | {no} | {nd} |")
    _write(os.path.join(ddir, "README.md"), "\n".join(T) + "\n")


# ---------------------------------------------------------------- 判断票

def _camel(col):
    p = col.split("_")
    return p[0] + "".join(x.title() for x in p[1:])


_CACHE = {}


def _files(project, sub):
    k = ("files", project, sub)
    if k not in _CACHE:
        out, root = [], os.path.join(project, sub)
        for dp, _, fs in os.walk(root):
            for f in sorted(fs):
                p = os.path.join(dp, f)
                out.append((os.path.relpath(p, project).replace(os.sep, "/"),
                            fio.read(p, errors="ignore").splitlines()))
        _CACHE[k] = sorted(out)
    return _CACHE[k]


def _test_refs(project, word):
    if not word:
        return []
    pat = re.compile(r"\b(" + re.escape(word) + "|" + re.escape(_camel(word)) + r")\b")
    hits = []
    for rel, lines in _files(project, os.path.join("src", "test")):
        n = [i + 1 for i, ln in enumerate(lines) if pat.search(ln)]
        if n:
            hits.append((rel, n))
    return hits


def _notes(project, srcs, word):
    out = []
    for s in srcs:
        if s.kind != "md" or not word:
            continue
        k = ("md", project, s.path)
        if k not in _CACHE:
            _CACHE[k] = fio.read(os.path.join(project, s.path)).splitlines()
        for i, ln in enumerate(_CACHE[k], 1):
            if ln.lstrip().startswith(("- ", "* ")) and re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", ln):
                out.append((f"{s.path}:{i}", ln.strip()[2:]))
    return out[:5]


def _git_index(project, paths):
    """関係するファイルの変更履歴を、git を1回だけ呼んで集める。"""
    k = ("gitidx", project)
    if k not in _CACHE:
        idx = {}
        try:
            r = subprocess.run(["git", "-C", project, "log", "--date=short", "--format=\x01%h %ad %s", "--name-only",
                                "--", *sorted(set(paths))], capture_output=True, text=True, timeout=60)
            order = 0
            for block in r.stdout.split("\x01")[1:]:
                lines = [x for x in block.splitlines() if x.strip()]
                if not lines:
                    continue
                order += 1
                for f in lines[1:]:
                    idx.setdefault(f.strip(), []).append((order, lines[0]))
        except Exception:
            pass
        _CACHE[k] = idx
    return _CACHE[k]


def _history(project, paths):
    idx = _CACHE.get(("gitidx", project), {})
    seen = {}
    for p in paths:
        for order, line in idx.get(p, []):
            seen[order] = line
    return [seen[o] for o in sorted(seen)][:3]


def _cmd(did, opt):
    return f"`banto decide {did} {opt} --by <名前> --reason \"<理由>\"`"


def write_drift(res, d):
    ddir = os.path.join(res.base, "drifts")
    path = os.path.join(ddir, f"{d.id}.md")
    if d.domain is None:
        return _write(path, _keep_notes(path, _review_sheet(res, d, ddir)))
    dom, spec = d.domain, d.attr
    tid = _target_id(res, d)
    where = f"{d.container}.{d.item}" if d.item else d.container
    if dom.name == "tests" and d.item:
        where = f"{d.container} › {d.item}"
    lc = res.ledgers[dom.name].get(d.container)
    ledger_path = os.path.join(res.base, dom.ledger_dir, LG.file_name(d.container))
    meta = OrderedDict(id=d.id, domain=dom.name, kind="only-in" if spec.name == "exists" else "conflict",
                       target=tid, attribute=spec.name, severity=d.severity, group=d.group, status=d.status)
    if d.decision:
        meta["decision"] = d.decision
    L = [frontmatter.dump(meta), f"# {d.id} {where} の{spec.label}", "",
         f"状態：**{STATUS_JA[d.status]}**　重要度：{SEV_JA[d.severity]}　グループ：{d.group_label}", ""]

    L += ["## 何がずれているか", "", "| 情報源 | 値 | 書かれ方 | 場所 | 台帳との差 |", "|---|---|---|---|---|"]
    L.append(f"| **台帳（banto）** | {spec.show(d.L) if d.L is not None else '未定'} | — | "
             f"[{_rel(ddir, ledger_path)}]({_rel(ddir, ledger_path)}) | — |")
    for s, f in d.facts:
        mark = "≠" if s.id in d.deviating else ("許容" if s.id in d.allowed else "")
        L.append(f"| {s.label} | {spec.show(f.value)} | {str(f.shown).replace('|', '¦')} | `{f.loc}` | {mark} |")
    silent = [s for s in res.sources[dom.name] if s.id not in {x.id for x, _ in d.facts}]
    if silent:
        why = "（この項目を持たない、またはこの属性を表さない）"
        L += ["", "比較に入っていない情報源：" + "、".join(s.label for s in silent) + why]

    L += ["", "## つながり", "", f"- 台帳：{tid or '（未登録）'} [{_rel(ddir, ledger_path)}]({_rel(ddir, ledger_path)})"]
    up = [(s, f) for s, f in d.facts if s.kind in DOC_KINDS]
    real = [(s, f) for s, f in d.facts if s.kind not in DOC_KINDS]
    L.append("- 上流（設計書）：" + ("、".join(f"{s.label} `{f.loc}`" for s, f in up) or "なし"))
    L.append("- 実物：" + ("、".join(f"{s.label} `{f.loc}`" for s, f in real) or "なし"))
    if dom.name == "tables":
        refs = _test_refs(res.project, d.item)
        if refs:
            L.append("- 下流（テストで触れている箇所）：")
            for p, ns in refs[:6]:
                L.append(f"  - `{p}` 行 {', '.join(map(str, ns[:8]))}{' …' if len(ns) > 8 else ''}")
            if len(refs) > 6:
                L.append(f"  - ほか {len(refs) - 6} ファイル")
        elif d.item:
            L.append("- 下流（テスト）：名前で触れている箇所なし")
    if dom.name == "tests" and lc and d.item in lc.items and lc.items[d.item].free.get("対象"):
        L.append(f"- 対象（台帳に書かれた検証対象）：{lc.items[d.item].free['対象']}")

    L += ["", "## 経緯", ""]
    word = (d.item.split("#")[-1] if d.item else d.container)
    for loc, text in _notes(res.project, res.sources[dom.name], word):
        L.append(f"- 設計書の記載 `{loc}`：{text}")
    paths = sorted({s.path for s, _ in d.facts}) + [os.path.relpath(ledger_path, res.project).replace(os.sep, "/")]
    hist = _history(res.project, paths)
    if hist:
        L.append("- 変更履歴（関係するファイル）：" + " ／ ".join(hist))
        if len(hist) == 1:
            L.append("  - 履歴が1件しかなく、いつ・なぜ食い違ったかは記録から辿れない")
    if spec.name == "exists":
        for s, f in d.facts:
            if s.scope_note and not f.value:
                L.append(f"- {s.label} の対象範囲：{s.scope_note}")
    for sid, (v, dec) in sorted(d.allowed.items()):
        L.append(f"- 許容済みの差：{sid} の「{spec.show(v)}」（{dec}）")
    e = res.state.drifts.get(d.key, {})
    for prev in e.get("previous", []):
        L.append(f"- 以前の判断：[{prev}](../decisions/{prev}.md)（その後、実物か台帳が変わり、再びずれた）")
    if L[-1] == "" or L[-1] == "## 経緯":
        L.append("- 手がかりなし")

    L += ["", "## 選択肢と影響", ""]
    if d.status == "open":
        cands = []
        if d.L is not None:
            cands.append(d.L)
        for _, f in d.facts:
            if not any(repr(f.value) == repr(x) for x in cands):
                cands.append(f.value)
        for n, v in enumerate(cands):
            need = [s for s, f in d.facts if repr(f.value) != repr(v)]
            if spec.name == "exists":
                verb = "追加する" if v else "取り除く"
                act = f"「{spec.show(v)}」とする（{', '.join(s.label for s in need) or 'なし'} で{verb}）"
            else:
                act = f"「{spec.show(v)}」を正とする" + ("（いまの台帳の値）" if n == 0 and d.L is not None else "")
                names = [s.label + ("（コードかテストを直して再実行）" if spec.authority and s.kind == spec.authority else "")
                         for s in need]
                act += f" → 直す必要：{'、'.join(names) or 'なし'}"
                if d.L is not None and repr(v) != repr(d.L) and not spec.authority:
                    act += "、台帳"
            L.append(f"- {chr(65 + n)}. {act}")
            L.append(f"  - {_cmd(d.id, '--set ' + _q(spec.show(v)))}")
        n = len(cands)
        if spec.name == "exists":
            L.append(f"- {chr(65 + n)}. 台帳には「あり」として載せ、記載のない情報源は対象範囲外として許容する（どれも変更しない）")
            L.append(f"  - {_cmd(d.id, '--allow --value あり')}")
        elif d.L is not None:
            example = "（DB方言の差、アプリとDBの役割分担など）" if dom.name == "tables" else ""
            L.append(f"- {chr(65 + n)}. 意図した違い{example}として許容する。台帳は「{spec.show(d.L)}」のまま、どれも変更しない")
            L.append(f"  - {_cmd(d.id, '--allow')}")
        else:
            L.append(f"- {chr(65 + n)}. 意図した違いとして許容する。台帳に載せる代表の値を選び、他の情報源の差は許容する（どれも変更しない）")
            L.append(f"  - {_cmd(d.id, '--allow --value <代表の値>')}")
        L += ["", f"同じグループ（{d.group_label}）をまとめて判断するとき：`banto decide --group \"{d.group}\" ...`"]
    else:
        L.append("（判断済み）")

    L += ["", "## 判断", ""]
    if d.status == "open":
        L.append("未判断。")
    else:
        L.append(f"[{d.decision}](../decisions/{d.decision}.md)" if d.decision else "（判断の記録なし。台帳の書き換えか、実物の修正で一致した）")
        if d.status == "decided":
            L += ["", f"直し待ち（「{spec.show(d.target)}」に合わせる）："]
            for s, f in d.facts:
                if s.id in d.deviating:
                    L.append(f"- {s.label} `{f.loc}`：いま「{spec.show(f.value)}」（{f.shown}）")
        else:
            L.append("")
            L.append("解決済み：いまは台帳とすべての情報源が一致している（許容した差を除く）。")
    _write(path, _keep_notes(path, "\n".join(L) + "\n"))


def _q(v):
    return '"' + str(v).replace('"', '\\"') + '"'


def _review_sheet(res, d, ddir):
    r = d.review
    meta = OrderedDict(id=d.id, domain="review", kind="review", target=r.get("target", ""), severity=d.severity,
                       status=d.status)
    if d.decision:
        meta["decision"] = d.decision
    L = [frontmatter.dump(meta), f"# {d.id} レビュー指摘 {r['doc']} No.{r['no']}", "",
         f"状態：**{STATUS_JA[d.status]}**", "", "## 指摘", "",
         f"- 対象文書・版：{r.get('docname') or '（未記入）'} 第{r.get('version') or '?'}版（レビュー {r['doc']}）",
         f"- 箇所：{r.get('target') or '（IDなし）'}{('　' + r['where']) if r.get('where') else ''}",
         f"- 種別：{r.get('type', '')}　重要度：{r.get('severity', '')}　指摘者：{r.get('reviewer', '')}",
         "", f"> {r.get('comment', '')}", ""]
    t = res.state.by_target_id().get(r.get("target", ""))
    L += ["## 指摘箇所の台帳の内容", ""]
    if t:
        dname, c, i = t
        from .domains import get
        dom = get(dname)
        lc = res.ledgers[dname].get(c)
        lp = os.path.join(res.base, dom.ledger_dir, LG.file_name(c))
        L.append(f"[{_rel(ddir, lp)}]({_rel(ddir, lp)})")
        if lc and i and i in lc.items:
            it = lc.items[i]
            L += ["", "| 属性 | 値 |", "|---|---|", f"| {dom.item_label} | `{i}` |"]
            for a in dom.item_attrs():
                v = it.values.get(a.name)
                L.append(f"| {a.label} | {a.show(v) if v is not None else '?（未定）'} |")
    else:
        L.append("箇所のIDが台帳に見つからない。指摘者に箇所を確認する。")
    L += ["", "## 選択肢", "",
          "- 指摘を受け入れ、台帳を直す", f"  - `banto decide {d.id} --accept --target <ID> --attr <属性名> --set <値> --by <名前> --reason \"<対応内容>\"`",
          "- 指摘を受け入れる（台帳の値は変えない。文言や説明の修正など）", f"  - `banto decide {d.id} --accept --by <名前> --reason \"<対応内容>\"`",
          "- 指摘を受け入れない", f"  - `banto decide {d.id} --reject --by <名前> --reason \"<理由>\"`",
          "- 質問に回答する", f"  - `banto decide {d.id} --answer --by <名前> --reason \"<回答>\"`", "",
          "## 判断", "", f"[{d.decision}](../decisions/{d.decision}.md)" if d.decision else "未判断。"]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 一覧

def write_index(res):
    ddir = os.path.join(res.base, "drifts")
    ds = res.drifts
    op = [d for d in ds if d.status == "open"]
    dc = [d for d in ds if d.status == "decided"]
    rs = [d for d in ds if d.status == "resolved"]
    sev = Counter(d.severity for d in op)
    L = ["# ずれの一覧", "",
         f"未判断 **{len(op)}** 件（高 {sev['high']}・中 {sev['medium']}・低 {sev['low']}）／ 直し待ち **{len(dc)}** 件 ／ 解決済み {len(rs)} 件", "",
         "bantoはどれが正かを決めない。判断票の材料を見て、人が決める。", "",
         "- 1件ずつ判断：`banto decide DRF-xxxx --set <値> --by <名前> --reason \"<理由>\"`",
         "- 同じグループをまとめて判断：`banto decide --group \"<グループ>\" --allow --by <名前> --reason \"<理由>\"`",
         "- 判断したら `banto sync` で台帳と判断票が更新される", ""]
    if res.errors:
        L += ["## 判断の記録の誤り", ""] + [f"- {e}" for e in res.errors] + [""]
    L += ["## 未判断（グループ別）", "", "同じグループは同じ規則でまとめて判断できる候補。", "",
          "| 重要度 | 領域 | グループ | 件数 | 判断票 |", "|---|---|---|---|---|"]
    groups = OrderedDict()
    rank = {"high": 0, "medium": 1, "low": 2}
    for d in sorted(op, key=lambda d: (0 if d.domain is None else 1, rank[d.severity], d.group, d.id)):
        groups.setdefault((d.severity, d.domain.title if d.domain else "レビュー", d.group, d.group_label), []).append(d)
    for (sv, dt, g, gl), items in groups.items():
        links = " ".join(f"[{d.id}]({d.id}.md)" for d in items[:12]) + (f" …ほか{len(items) - 12}件" if len(items) > 12 else "")
        L.append(f"| {SEV_JA[sv]} | {dt} | {gl}<br>`{g}` | {len(items)} | {links} |")
    L += ["", "## 直し待ち", "", "判断済みで、実物（コード・DB・文書）の修正を待っているもの。作業の一覧は [APPLY.md](APPLY.md)。", ""]
    if dc:
        L += ["| ID | 対象 | 属性 | 台帳の値 | 判断 |", "|---|---|---|---|---|"]
        for d in dc:
            where = f"{d.container}.{d.item}" if d.item else d.container
            L.append(f"| [{d.id}]({d.id}.md) | {where} | {d.attr.label} | {d.attr.show(d.L)} | {d.decision} |")
    else:
        L.append("なし")
    L += ["", "## 解決済み", "", ("、".join(f"[{d.id}]({d.id}.md)" for d in rs) or "なし"), ""]
    _write(os.path.join(ddir, "README.md"), "\n".join(L))


def write_apply(res):
    ddir = os.path.join(res.base, "drifts")
    dc = [d for d in res.drifts if d.status == "decided" and d.domain is not None]
    by_src = OrderedDict()
    for d in dc:
        for s, f in d.facts:
            if s.id in d.deviating:
                by_src.setdefault((s.id, s.label), []).append((d, f))
    L = ["# 直し待ちの作業", "",
         "判断どおりに実物を直す作業の一覧。直したら `banto sync` で確認すると、一致したものは解決済みになる。",
         "判断の中身は変えないこと。判断に疑問があれば、直さずに判断した人に戻す。", ""]
    if not by_src:
        L.append("なし")
    for (sid, label), items in by_src.items():
        L += [f"## {label}（{sid}）", "", "| ずれ | 対象 | 属性 | 場所 | いま | あるべき値 | 判断 |", "|---|---|---|---|---|---|---|"]
        for d, f in items:
            where = f"{d.container}.{d.item}" if d.item else d.container
            if d.attr.name == "exists":
                want = "追加する" if d.target else "取り除く"
            else:
                want = d.attr.show(d.target)
            L.append(f"| [{d.id}]({d.id}.md) | {where} | {d.attr.label} | `{f.loc}` | {str(f.shown).replace('|', '¦')} | {want} | {d.decision} |")
        L.append("")
    _write(os.path.join(ddir, "APPLY.md"), "\n".join(L) + "\n")
