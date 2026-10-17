"""網羅の確認：様式の各項目について、設計書を作るのに必要な情報が揃っているかを仕分ける。

  該当するか … 必要 / 該当（手がかりあり）/ 不要の候補（手がかりなし）/ 不要・必要（人の判断 DEC）
  揃っているか … 充足 / 情報不足（何が、どこで、いくつ足りないか）
不要かどうかはbantoが決めない。手がかりがなければ「不要の候補」として根拠を示し、人が判断する。
"""
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from . import formats, frontmatter, manual, project as PJ
from .domains import get

NEED = ("必要", "該当", "必要（判断済み）")


@dataclass
class Cov:
    doc: dict
    item: dict
    applicability: str
    evidence: str = ""
    decision: str = ""
    sufficiency: str = "—"
    details: list = field(default_factory=list)   # 足りないものの要約（行）
    missing: list = field(default_factory=list)   # (ID, 名前, 項目) の一覧
    where: str = ""                               # 書く場所（台帳ファイル・人が書く節）

    @property
    def id(self):
        return self.item["id"]

    @property
    def needed(self):
        return self.applicability in NEED


def compute(res, write=False):
    cfg = PJ.load(res.base)
    fmt = formats.load(res.base, cfg.get("format", "standard"))
    scan = formats.Scanner(res.project)
    out = []
    for doc, it in formats.items(fmt):
        dec = res.state.coverage.get(it["id"])
        if dec:
            c = Cov(doc, it, "必要（判断済み）" if dec["applicable"] else "不要（判断済み）", decision=dec["decision"])
        elif it.get("signals"):
            hit = next((h for h in (scan.match(s) for s in it["signals"]) if h), None)
            c = Cov(doc, it, "該当" if hit else "不要の候補",
                    evidence=(f"手がかり：`{hit}`" if hit else
                              "手がかりなし：" + "、".join(scan.describe(s) for s in it["signals"]) + " が見つからない"))
        else:
            c = Cov(doc, it, "必要")
        _sufficiency(res, c, write)
        out.append(c)
    res.format = fmt
    return out


def _label(dom, fname):
    if fname.startswith("free:"):
        return fname[5:]
    return dom.attrs[fname].label


def _value(obj, fname):
    if fname.startswith("free:"):
        v = obj.free.get(fname[5:], "")
        return v if v.strip() else None
    return obj.values.get(fname) if hasattr(obj, "values") else obj.attrs.get(fname)


def _sufficiency(res, c, write):
    it, kind = c.item, c.item["kind"]
    if kind in ("text", "manual-table"):
        c.where = os.path.relpath(manual.path(res.base, it["id"]), res.project).replace(os.sep, "/")
        m = manual.load(res.base, it["id"])
        if m is None and write and c.needed:
            from . import fio
            fio.write(manual.path(res.base, it["id"]), manual.skeleton(c.doc, it))
            m = manual.load(res.base, it["id"])
        if not c.needed:
            return
        if m is None:
            c.sufficiency, c.details = "情報不足", ["まだ書かれていない"]
        elif kind == "text":
            text = manual.prose(m["body"])
            ok = len(text) >= 20
            c.sufficiency = "充足" if ok else "情報不足"
            if not ok:
                c.details = ["本文がない（ひな形のまま）" if not text else f"本文が短すぎる（{len(text)}文字）"]
        else:
            rows, req = m["rows"], it.get("required", [])
            if not rows:
                c.sufficiency, c.details = "情報不足", ["行がない"]
            else:
                blanks = [(f"{n}行目", r.get(it["columns"][0], ""), col) for n, r in enumerate(rows, 1) for col in req
                          if not (r.get(col) or "").strip()]
                c.missing = blanks
                c.sufficiency = "情報不足" if blanks else "充足"
                c.details = [f"{len(rows)}行"] + ([f"必須の列の空欄 {len(blanks)}か所"] if blanks else [])
        if m and m["meta"].get("status") != "confirmed" and c.sufficiency == "充足":
            c.details.append("status が confirmed になっていない（確認待ち）")
        return
    if kind == "ref":
        c.where = f"{it['document']}（別冊）"
        if c.needed:
            c.sufficiency = "参照"
        return
    dom = get(it["domain"])
    ledger = res.ledgers.get(it["domain"], {})
    c.where = dom.ledger_dir + "/"
    if not c.needed:
        return
    conts = sorted((lc for lc in ledger.values() if lc.status not in ("removed", "removing")), key=lambda lc: lc.id)
    pending = {d.key for d in res.drifts if d.domain is dom and d.status == "open"}

    def missing(lc, i, f):
        """値が空なら足りない。ただし未判断のずれで空になっているものは「判断待ち」として数えない。"""
        obj = lc if i is None else i
        if _value(obj, f) not in (None, ""):
            return False
        if i is not None and f in ("length", "scale"):
            # 長さは文字列と数値型、小数桁は数値型のときだけ要る
            bt = i.values.get("base_type")
            if bt not in (("string", "decimal") if f == "length" else ("decimal",)):
                return False
        return f"{dom.name}|{lc.name}|{'' if i is None else i.name}|{f}" not in pending
    counts = OrderedDict()
    creq = it.get("container_required", []) if kind == "ledger-table" else it.get("required", [])
    for f in creq:
        miss = [lc for lc in conts if missing(lc, None, f)]
        counts[f"{dom.container_label}の{_label(dom, f)}"] = (len(conts) - len(miss), len(conts))
        c.missing += [(lc.id, lc.name, _label(dom, f)) for lc in miss]
    if kind == "ledger-table":
        items = [(lc, i) for lc in conts for i in lc.items.values() if i.exists is not False]
        for f in it.get("required", []):
            miss = [(lc, i) for lc, i in items if missing(lc, i, f)]
            counts[_label(dom, f)] = (len(items) - len(miss), len(items))
            c.missing += [(i.id, f"{lc.name}.{i.name}", _label(dom, f)) for lc, i in miss]
    op = sum(1 for d in res.drifts if d.domain is dom and d.status == "open")
    dc = sum(1 for d in res.drifts if d.domain is dom and d.status == "decided")
    lacking = [f"{k} {a}/{n}" for k, (a, n) in counts.items() if a < n]
    c.details = lacking + ([f"未判断のずれ {op}件"] if op else []) + ([f"直し待ち {dc}件"] if dc else [])
    if not conts:
        c.details.insert(0, f"{dom.container_label}がない")
    c.sufficiency = "情報不足" if (lacking or op or not conts) else "充足"
    if c.sufficiency == "充足" and dc:
        c.details.append("（直し待ちは実物側の作業。台帳の情報は揃っている）")


# ---------------------------------------------------------------- 書き出し

FILL_HINT = {
    "logical_name": "既存の設計書の「論理名」列、DBのコメント（sources.json の comment_as）から取り込むか、台帳の「論理名」列に書く",
    "description": "既存の設計書の「説明・備考」列、DBのコメントから取り込むか、台帳の「説明」列に書く",
    "title": "テーブル論理名。DBのテーブルコメントか、設計書の見出し「論理名（物理名）」から取り込むか、台帳の属性表に書く",
    "expected": "テスト仕様書に「期待結果」列を足して取り込むか、台帳の「期待結果」列に書く。テストコードのアサーションから extractor が下書きできる",
    "precondition": "テスト仕様書の「前提条件」列から取り込むか、台帳に書く",
    "steps": "テスト仕様書の「手順」列から取り込むか、台帳に書く",
    "level": "テストクラスごとに「単体」「結合」「総合」などを台帳の属性表に書く",
    "summary": "テスト仕様書の「目的」節（sources.json の sections）から取り込むか、台帳に書く",
}


def write(res, covs):
    from . import fio
    from .writer import _keep_notes, _write
    cdir = os.path.join(res.base, "coverage")
    cfg = PJ.load(res.base)
    authors = "、".join(PJ.people_with(cfg, "author")) or "（作成者の登録なし）"
    judges = "、".join(PJ.people_with(cfg, "judge")) or "（判断者の登録なし）"
    fmt = res.format
    n = {k: 0 for k in ("充足", "情報不足", "不要の候補", "不要（判断済み）")}
    for c in covs:
        if c.applicability in ("不要の候補", "不要（判断済み）"):
            n[c.applicability] += 1
        elif c.sufficiency in n:
            n[c.sufficiency] += 1
    L = [f"# 網羅表（様式：{fmt['title']}）", "",
         f"充足 **{n['充足']}**・情報不足 **{n['情報不足']}**・不要の候補 **{n['不要の候補']}**・不要（判断済み） {n['不要（判断済み）']}", "",
         "設計書を作るのに必要な情報が揃っているかの一覧。不要かどうかは人が判断する（`banto decide --item <ID> --exclude|--include`）。", ""]
    for doc in fmt["documents"]:
        L += [f"## {doc['id']} {doc['title']}", "", "| ID | 項目 | 該当 | 充足 | 詳細 | 根拠 |", "|---|---|---|---|---|---|"]
        for c in covs:
            if c.doc is not doc:
                continue
            link = f"[{c.id}]({c.id}.md)" if _has_sheet(c) else c.id
            det = "、".join(c.details) if c.needed else ""
            why = c.decision and f"[{c.decision}](../decisions/{c.decision}.md)" or c.evidence.replace("|", "¦")
            L.append(f"| {link} | {c.item['title']} | {c.applicability} | {c.sufficiency} | {det} | {why} |")
        L.append("")
    _write(os.path.join(cdir, "README.md"), "\n".join(L))
    for c in covs:
        if _has_sheet(c):
            p = os.path.join(cdir, f"{c.id}.md")
            _write(p, _keep_notes(p, _sheet(res, c, authors, judges)))


def _has_sheet(c):
    return c.applicability == "不要の候補" or (c.needed and c.sufficiency == "情報不足")


def _sheet(res, c, authors, judges):
    it = c.item
    kind = "不要の候補" if c.applicability == "不要の候補" else "情報不足"
    meta = OrderedDict(id=c.id, kind=kind, document=c.doc["title"], title=it["title"], applicability=c.applicability,
                       sufficiency=c.sufficiency)
    L = [frontmatter.dump(meta), f"# {c.id} {it['title']}（{kind}）", "", f"文書：{c.doc['title']}", ""]
    if kind == "不要の候補":
        L += ["## なぜ候補か", "", c.evidence, "",
              "この項目は、このシステムに該当しない可能性がある。手がかりは機械的な検索なので、該当しないと言い切れるのは人だけ。", "",
              "## 選択肢", "",
              "- 不要と判断する（設計書には「対象外」と理由つきで載る）",
              f"  - `banto decide --item {c.id} --exclude --by <名前> --reason \"<理由>\"`",
              "- 必要と判断する（手がかりが拾えていないだけ。以後は情報不足として追跡する）",
              f"  - `banto decide --item {c.id} --include --by <名前> --reason \"<理由>\"`", "",
              f"判断する人：{judges}", ""]
        return "\n".join(L)
    L += ["## 必要な情報", ""]
    if it["kind"] == "manual-table":
        L.append("列：" + "、".join(it["columns"]) + "（必須：" + "、".join(it.get("required", [])) + "）")
    elif it["kind"] == "text":
        L.append(it.get("hint", ""))
    else:
        dom = get(it["domain"])
        fields = [_label(dom, f) for f in it.get("fields", [])]
        req = [_label(dom, f) for f in it.get("required", [])]
        creq = [_label(dom, f) for f in it.get("container_required", [])]
        L.append(f"{dom.item_label if it['kind'] == 'ledger-table' else dom.container_label}ごとに：" + "、".join(fields))
        L.append("必須：" + "、".join((creq and [f"{dom.container_label}の" + x for x in creq] or []) + req))
    L += ["", "## 足りないもの", ""] + [f"- {d}" for d in c.details]
    if c.missing:
        L += ["", "| ID | 対象 | 足りない項目 |", "|---|---|---|"]
        for tid, name, f in c.missing[:40]:
            L.append(f"| {tid} | `{name}` | {f} |")
        if len(c.missing) > 40:
            L.append(f"| … | ほか {len(c.missing) - 40} 件 | |")
    L += ["", "## 埋め方", "", f"- 書く場所：`{c.where}`", f"- 取り方：{it.get('how', '人が書く')}"]
    if it["kind"] in ("ledger-list", "ledger-table"):
        seen = set()
        for f in list(it.get("container_required", [])) + list(it.get("required", [])):
            key = f[5:] if f.startswith("free:") else f
            if key in FILL_HINT and key not in seen:
                seen.add(key)
                L.append(f"- {_label(get(it['domain']), f)}：{FILL_HINT[key]}")
        if any("未判断" in d for d in c.details):
            L.append("- 未判断のずれは `banto/drifts/README.md` から判断する（判断票）")
    L += [f"- 担当：{authors}", "",
          "推定（extractor の下書きなど）で埋めたときは、人が確かめるまで「（推定）」と書き添える。", ""]
    return "\n".join(L)
