"""台帳と人が書いた節から、様式どおりのExcelを清書する（banto export）。

台帳MDと banto/manual/ が原本で、Excelは提出用の写し。本体のシートは保護（パスワードなし）して直接の編集を防ぎ、
指摘はレビュー表に書いてもらう。各行には台帳への対応（banto-ref）を非表示列で持つ。
版は、文書の中身が前回の出力から変わったときだけ上がり、改訂履歴に「何が変わったか」と判断した人が残る。
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from . import engine, fio, ledger as LG, manual, project as PJ
from .coverage import _label, _value
from .domains import get

FONT = "Yu Gothic"
HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
WARN_FILL = PatternFill("solid", fgColor="FFF2CC")
OPEN_FILL = PatternFill("solid", fgColor="FCE4D6")
GRAY = PatternFill("solid", fgColor="EDEDED")
THIN = Side(style="thin", color="A6A6A6")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
SEV_JA = {"high": "高", "medium": "中", "low": "低"}
STATUS_JA = {"open": "未判断", "decided": "直し待ち", "resolved": "解決済み"}


def _f(bold=False, size=10, color=None):
    return Font(name=FONT, bold=bold, size=size, color=color)


def _sheet_title(name, used):
    t = re.sub(r"[\[\]:*?/\\]", "_", name)[:31] or "sheet"
    base, n = t, 2
    while t in used:
        suffix = f"~{n}"
        t = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(t)
    return t


def _table(ws, row, headers, rows, widths=None, fills=None, col=1):
    for c, h in enumerate(headers, col):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font, cell.fill, cell.border = _f(True), HEAD_FILL, BOX
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for r, vals in enumerate(rows, row + 1):
        for c, v in enumerate(vals, col):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font, cell.border = _f(), BOX
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if fills and fills[r - row - 1]:
                cell.fill = fills[r - row - 1]
    if widths:
        for c, w in enumerate(widths, col):
            ws.column_dimensions[get_column_letter(c)].width = w
    return row + len(rows) + 1


def _print_setup(ws, title):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.oddHeader.center.text = title
    ws.oddFooter.center.text = "&P / &N"


def _git_head(project):
    try:
        r = subprocess.run(["git", "-C", project, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or "（Git管理外）"
    except Exception:
        return "（Git管理外）"


# ---------------------------------------------------------------- 文書の中身（版と差分のもと）

def content(res, doc, covs):
    """文書に載る中身を {キー: 値} にする。版の判定と、前回からの差分に使う（日時は含めない）。"""
    out = {}
    for it in doc["items"]:
        c = covs.get(it["id"])
        iid = it["id"]
        out[f"{iid}|該当"] = c.applicability if c else ""
        if c and not c.needed:
            continue
        k = it["kind"]
        if k == "text":
            m = manual.load(res.base, iid)
            out[f"{iid}|本文"] = manual.prose(m["body"]) if m else ""
        elif k == "manual-table":
            m = manual.load(res.base, iid)
            for n, r in enumerate(m["rows"] if m else [], 1):
                out[f"{iid}|{n}行目"] = " / ".join(r.get(col, "") for col in it["columns"])
        elif k in ("ledger-list", "ledger-table"):
            dom = get(it["domain"])
            for lc in _containers(res, it["domain"]):
                cfields = it.get("fields", []) if k == "ledger-list" else it.get("container_fields", [])
                for f in cfields:
                    out[f"{iid}|{lc.name}|{_label(dom, f)}"] = _show(dom, lc, f)
                if k == "ledger-table":
                    for i in lc.items.values():
                        for f in it.get("fields", []):
                            out[f"{iid}|{lc.name}.{i.name}|{_label(dom, f)}"] = _show(dom, i, f)
    return out


def _containers(res, dname):
    return sorted((lc for lc in res.ledgers.get(dname, {}).values() if lc.status not in ("removed",)), key=lambda lc: lc.id)


_CFG = {}


def _show(dom, obj, f):
    v = _value(obj, f)
    if f.startswith("free:"):
        return v or ""
    return PJ.display(_CFG, dom.attrs[f], v)


def _diff(old, new, limit=30):
    lines = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        where = k.replace("|", " ")
        if a is None:
            lines.append(f"追加：{where}「{b}」")
        elif b is None:
            lines.append(f"削除：{where}")
        else:
            lines.append(f"変更：{where}「{a}」→「{b}」")
    more = len(lines) - limit
    return lines[:limit] + ([f"ほか {more} 件"] if more > 0 else []), len(lines)


def versions_path(base):
    return os.path.join(base, "state", "versions.json")


def load_versions(base):
    p = versions_path(base)
    return json.loads(fio.read(p)) if os.path.exists(p) else {}


def save_versions(base, data):
    fio.write(versions_path(base), json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def _version(res, doc, cont):
    """中身が前回の出力から変わっていれば版を上げ、改訂履歴に変更の内容と判断した人を残す。"""
    data = load_versions(res.base)
    v = data.setdefault(doc["id"], {"version": 0, "hash": "", "history": [], "decisions": [], "snapshot": {}, "released": []})
    digest = hashlib.sha256(json.dumps(cont, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    if v["hash"] != digest:
        applied = sorted(set(res.state.applied) - set(v.get("decisions", [])))
        by = sorted({d.decided_by for d in res.decisions if d.id in applied and d.decided_by})
        changes, n = _diff(v.get("snapshot", {}), cont) if v["version"] else ([], 0)
        v["version"] += 1
        v["hash"] = digest
        note = "初版" if v["version"] == 1 else f"{n}件の変更" + ("（判断の反映：" + "、".join(applied) + "）" if applied else "")
        v["history"].append({"version": v["version"], "date": datetime.date.today().isoformat(), "note": note,
                             "decisions": applied, "by": "、".join(by), "changes": changes})
        v["decisions"] = sorted(res.state.applied)
        v["snapshot"] = cont
        save_versions(res.base, data)
    return v


# ---------------------------------------------------------------- 出力

def export(project, out=None, only=None):
    res = engine.sync(project)
    cfg = PJ.load(res.base)
    _CFG.clear()
    _CFG.update(cfg)
    out = out or os.path.join(res.base, "export")
    os.makedirs(out, exist_ok=True)
    head = _git_head(project)
    covs = {c.id: c for c in res.coverage}
    fmt = res.format
    files, versions = [], {}
    is_custom = cfg.get("format", "standard").startswith("custom:")
    for doc in fmt["documents"]:
        if only and doc["id"] not in only:
            continue
        cont = content(res, doc, covs)
        v = _version(res, doc, cont)
        versions[doc["title"]] = v["version"]
        if not is_custom:
            path = os.path.join(out, f"{doc['id']}_{doc['title']}.xlsx")
            _book(res, cfg, fmt, doc, covs, v, head, path)
            files.append(path)
    if is_custom:
        from . import custom
        files += custom.export(res, cfg, out, versions)
    files.append(_review_book(res, fmt, versions, out))
    return files


def _book(res, cfg, fmt, doc, covs, ver, head, path):
    wb = Workbook()
    used = set()
    items = doc["items"]
    domains = {it["domain"] for it in items if it.get("domain")}
    drifts = [d for d in res.drifts if d.domain is not None and d.domain.name in domains and d.status != "resolved"]
    lacking = [covs[it["id"]] for it in items if it["id"] in covs and covs[it["id"]].needed
               and covs[it["id"]].sufficiency == "情報不足"]
    released = ver.get("released", [])
    last = released[-1] if released else None
    # 表紙
    ws = wb.active
    ws.title = _sheet_title("表紙", used)
    ws["B3"], ws["B3"].font = doc["title"], _f(True, 20)
    ws["B4"], ws["B4"].font = cfg.get("system") or os.path.basename(os.path.abspath(res.project)), _f(size=14)
    info = [("案件", cfg.get("project", "")), ("顧客", cfg.get("customer", "")), ("版", f"第{ver['version']}版"),
            ("作成日", datetime.date.today().isoformat()), ("作成者", "、".join(PJ.people_with(cfg, "author"))),
            ("承認者", (f"{last['by']}（第{last['version']}版を {last['date']} に承認）" if last else "（未承認）")),
            ("様式", fmt["title"]), ("生成元", f"banto台帳／コミット {head}"),
            ("未判断・直し待ちのずれ", len(drifts)), ("情報不足の項目", len(lacking))]
    for n, (k, val) in enumerate(info, 6):
        ws.cell(row=n, column=2, value=k).font = _f(True)
        c = ws.cell(row=n, column=3, value=val)
        c.font, c.alignment = _f(), Alignment(horizontal="left")
        if k in ("未判断・直し待ちのずれ", "情報不足の項目") and val:
            c.fill = WARN_FILL
    for n, text in enumerate(["このファイルはbantoの台帳（MD）から自動生成した写しです。直接編集しないでください。",
                              "指摘は、同時に出力したレビュー表に、各シートのIDを添えて記入してください。"], 18):
        ws.cell(row=n, column=2, value=text).font = _f(color="C00000")
    ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 22, 64
    _print_setup(ws, doc["title"])
    # 改訂履歴
    ws = wb.create_sheet(_sheet_title("改訂履歴", used))
    rel = {r["version"]: r for r in released}
    rows = []
    for h in ver["history"]:
        r = rel.get(h["version"])
        rows.append([f"第{h['version']}版", h["date"], h["note"] + ("\n" + "\n".join(h.get("changes", [])) if h.get("changes") else ""),
                     h.get("by", ""), f"承認：{r['by']}（{r['date']}）" if r else ""])
    _table(ws, 1, ["版", "日付", "内容", "判断した人", "提出"], rows, [9, 12, 80, 14, 24])
    _print_setup(ws, f"{doc['title']} 改訂履歴")
    # 目次
    ws = wb.create_sheet(_sheet_title("目次", used))
    rows, fills, sheets = [], [], {}
    for n, it in enumerate(items, 1):
        c = covs.get(it["id"])
        if it["kind"] == "ref":
            st = f"別冊「{_doc_title(fmt, it['document'])}」を参照"
        elif c and c.applicability == "不要の候補":
            st = "不要の候補（要・不要が未判断）"
        elif c and not c.needed:
            st = "対象外（" + (_reason(res, c) or "判断済み") + "）"
        elif c and c.sufficiency == "情報不足":
            st = "情報不足：" + "、".join(c.details)
        else:
            st = "記載"
        if it["kind"] != "ref" and (not c or c.needed):
            sheets[it["id"]] = _sheet_title(f"{it['id']} {it['title']}", used)
        rows.append([n, it["id"], it["title"], st, sheets.get(it["id"], "")])
        fills.append(OPEN_FILL if st.startswith("情報不足") else GRAY if st.startswith("対象外") else
                     WARN_FILL if st.startswith("不要の候補") else None)
    _table(ws, 1, ["No", "ID", "項目", "状態", "シート"], rows, [6, 9, 30, 70, 30], fills)
    _print_setup(ws, f"{doc['title']} 目次")
    # 本体
    by_key = {d.key: d for d in res.drifts}
    for it in items:
        if it["id"] not in sheets:
            continue
        ws = wb.create_sheet(sheets[it["id"]])
        ws["A1"], ws["A1"].font = f"{it['id']} {it['title']}", _f(True, 14)
        c = covs.get(it["id"])
        if c and c.sufficiency == "情報不足":
            ws["A2"], ws["A2"].font = f"情報不足：{'、'.join(c.details)}（banto/coverage/{it['id']}.md）", _f(color="C00000")
        r = 4
        k = it["kind"]
        if k == "text":
            m = manual.load(res.base, it["id"])
            text = manual.prose(m["body"]) if m else ""
            for line in (text.splitlines() or ["（未記入）"]):
                cell = ws.cell(row=r, column=1, value=line)
                cell.font, cell.alignment = _f(), Alignment(wrap_text=True, vertical="top")
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
                r += 1
            for col in range(1, 9):
                ws.column_dimensions[get_column_letter(col)].width = 14
        elif k == "manual-table":
            m = manual.load(res.base, it["id"])
            rws = m["rows"] if m else []
            req = set(it.get("required", []))
            data = [[row.get(col, "") for col in it["columns"]] for row in rws] or [["（未記入）"] + [""] * (len(it["columns"]) - 1)]
            fills = [OPEN_FILL if any(not (row.get(col) or "").strip() for col in req) else None for row in rws] or [OPEN_FILL]
            _table(ws, r, it["columns"], data, [max(12, min(40, len(cn) * 3 + 6)) for cn in it["columns"]], fills)
        elif k == "ledger-list":
            dom = get(it["domain"])
            rows, fills = [], []
            for n, lc in enumerate(_containers(res, it["domain"]), 1):
                vals = [_show(dom, lc, f) for f in it.get("fields", [])]
                miss = any(_value(lc, f) in (None, "") for f in it.get("required", []))
                rows.append([n, lc.id, lc.name] + [x or "—" for x in vals])
                fills.append(OPEN_FILL if miss else None)
            _table(ws, r, ["No", "ID", dom.container_label] + [_label(dom, f) for f in it.get("fields", [])],
                   rows, [6, 10, 26] + [28] * len(it.get("fields", [])), fills)
        elif k == "ledger-table":
            ws.cell(row=r, column=1, value=f"{get(it['domain']).container_label}ごとのシートに続く。").font = _f(color="595959")
            _ledger_sheets(res, wb, used, it, by_key)
        _print_setup(ws, f"{doc['title']} {it['title']}")
        ws.protection.sheet = True
    # 未判断・情報不足
    ws = wb.create_sheet(_sheet_title("未判断・情報不足", used))
    rows = [[d.id, f"{d.container}.{d.item}" if d.item else d.container, d.attr.label, SEV_JA[d.severity],
             STATUS_JA[d.status], d.group_label] for d in drifts]
    rows += [[c.id, c.item["title"], "—", "—", "情報不足", "、".join(c.details)] for c in lacking]
    _table(ws, 1, ["ID", "対象", "属性", "重要度", "状態", "内容"], rows or [["（なし）", "", "", "", "", ""]], [11, 40, 14, 8, 10, 60])
    _print_setup(ws, f"{doc['title']} 未判断・情報不足")
    for w in wb.worksheets:
        if w.title != "表紙":
            w.sheet_view.zoomScale = 90
    wb.save(path)


def _doc_title(fmt, did):
    return next((d["title"] for d in fmt["documents"] if d["id"] == did), did)


def _reason(res, c):
    if not c.decision:
        return ""
    dec = next((d for d in res.decisions if d.id == c.decision), None)
    return f"{c.decision}：{dec.reason}" if dec else c.decision


def _cell(a, v, d):
    shown = PJ.display(_CFG, a, v)
    if d and d.status == "open":
        return f"未定（{d.id}）" if v is None else f"{shown}（{d.id} 未判断）"
    if d and d.status == "decided":
        return f"{shown}（{d.id} 直し待ち）"
    return shown if v is not None else "—"


def _ledger_sheets(res, wb, used, it, by_key):
    dom = get(it["domain"])
    fields = it.get("fields", [])
    cfields = it.get("container_fields", [])
    req = set(it.get("required", []))
    for lc in _containers(res, it["domain"]):
        ws = wb.create_sheet(_sheet_title(lc.name, used))
        title = lc.attrs.get("title")
        ws["A1"], ws["A1"].font = f"{dom.container_label}：{lc.name}" + (f"（{title}）" if title else ""), _f(True, 14)
        ws["A2"], ws["A2"].font = f"ID：{lc.id}", _f()
        r = 4
        if cfields:
            crow = []
            for f in cfields:
                d = by_key.get(f"{dom.name}|{lc.name}||{f}")
                crow.append([_label(dom, f), _cell(dom.attrs[f], lc.attrs.get(f), d) if not f.startswith("free:") else _show(dom, lc, f)])
            r = _table(ws, r, ["属性", "値"], crow, None) + 1
        heads = ["ID", dom.item_label] + [_label(dom, f) for f in fields] + ["状態", "banto-ref"]
        lrel = os.path.relpath(os.path.join(res.base, dom.ledger_dir, LG.file_name(lc.name)), res.project).replace(os.sep, "/")
        rows, fills = [], []
        for iname, i in lc.items.items():
            row = [i.id, iname]
            flag = False
            for f in fields:
                if f.startswith("free:"):
                    row.append(_show(dom, i, f))
                    flag |= f in req and not _show(dom, i, f)
                    continue
                d = by_key.get(f"{dom.name}|{lc.name}|{iname}|{f}")
                row.append(_cell(dom.attrs[f], i.values.get(f), d))
                flag |= bool(d and d.status == "open") or (f in req and i.values.get(f) is None)
            ed = by_key.get(f"{dom.name}|{lc.name}|{iname}|exists")
            st = "有無が未判断" if i.exists is None else ("削除予定" if i.exists is False else "")
            if ed and ed.status != "resolved":
                st += f"（{ed.id}）"
                flag = True
            row += [st or ("未確定あり" if flag else "確定"), f"{lrel}#{i.id}"]
            rows.append(row)
            fills.append(OPEN_FILL if flag else None)
        widths = [10, 30] + [48 if f in ("purpose", "steps", "expected", "precondition", "description") else
                             max(12, len(_label(dom, f)) * 2 + 6) for f in fields] + [14, 30]
        _table(ws, r, heads, rows, widths, fills)
        ws.column_dimensions[get_column_letter(len(heads))].hidden = True
        ws.freeze_panes = ws.cell(row=r + 1, column=3)
        _print_setup(ws, f"{dom.container_label} {lc.name}")
        ws.protection.sheet = True


def _review_book(res, fmt, versions, out):
    wb = Workbook()
    st = res.state
    n = st.ids["counters"].get("RV", 0) + 1
    st.ids["counters"]["RV"] = n
    st.save()
    rid = f"RV{n:03d}"
    ws = wb.active
    ws.title = "レビュー表"
    docs = list(versions)
    heads = ["指摘No", "対象文書", "版", "箇所（ID）", "箇所の補足（シート・行など）", "指摘内容", "種別", "重要度", "指摘者",
             "対応方針", "対応内容", "反映版", "確認者", "ステータス"]
    ws["A1"], ws["A1"].font = f"レビュー表（{rid}）", _f(True, 14)
    ws["A2"] = "記入するのは「対象文書」〜「指摘者」まで。箇所は各シートのID（TBL-・COL-・TSU-・TC-、または項目ID BD-01 など）で指してください。"
    ws["A2"].font = _f(color="595959")
    vmap = "".join(f'IF(B{{r}}="{d}",{versions[d]},' for d in docs) + '""' + ")" * len(docs)
    rows = [[i, "", f"={vmap.format(r=i + 3)}"] + [""] * 11 for i in range(1, 101)]
    _table(ws, 3, heads, rows, [7, 16, 6, 12, 22, 60, 8, 7, 12, 12, 30, 7, 10, 10])
    ws.freeze_panes = "B4"
    for col, vals in {"B": docs, "G": ["誤り", "漏れ", "表現", "質問", "その他"], "H": ["高", "中", "低"],
                      "N": ["未対応", "対応済み", "確認済み"]}.items():
        dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}4:{col}103")
    wi = wb.create_sheet("ID一覧")
    rows = []
    for doc in fmt["documents"]:
        for it in doc["items"]:
            rows.append([it["id"], doc["title"], it["title"], ""])
    for dname, ledger in res.ledgers.items():
        dom = get(dname)
        for lc in _containers(res, dname):
            rows.append([lc.id, dom.title, lc.name, ""])
            for iname, it in lc.items.items():
                rows.append([it.id, dom.title, lc.name, iname])
    _table(wi, 1, ["ID", "文書", "項目・テーブル・テストクラス", "列・テスト"], rows, [10, 16, 36, 48])
    wi.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1=f"=ID一覧!$A$2:$A${len(rows) + 1}", allow_blank=True)
    dv.error, dv.showErrorMessage = "ID一覧にあるIDを入力してください", True
    ws.add_data_validation(dv)
    dv.add("D4:D103")
    wp = wb.create_sheet("これまでの指摘と対応")
    decs = {d.id: d for d in res.decisions}
    rows = []
    for d in res.drifts:
        if d.domain is None:
            r = d.review
            dec = decs.get(d.decision)
            act = {"accept": "対応する", "reject": "対応しない", "answer": "回答"}.get(dec.action, "") if dec else ""
            rows.append([f"{r['doc']}-{r['no']}", r.get("target", ""), r.get("comment", ""), act,
                         dec.reason if dec else "", STATUS_JA[d.status], d.id])
    _table(wp, 1, ["指摘", "箇所", "指摘内容", "対応方針", "対応内容", "状態", "判断票"], rows or [["（なし）"] + [""] * 6],
           [12, 10, 50, 10, 40, 10, 11])
    wm = wb.create_sheet("banto")
    wm["A1"], wm["B1"] = "review_id", rid
    for i, (d, v) in enumerate(versions.items(), 2):
        wm.cell(row=i, column=1, value=f"version:{d}")
        wm.cell(row=i, column=2, value=v)
    wm.sheet_state = "hidden"
    for w in (ws, wi, wp):
        _print_setup(w, f"レビュー表 {rid}")
    path = os.path.join(out, f"review-{rid}.xlsx")
    wb.save(path)
    return path
