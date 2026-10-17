"""同期: 情報源から事実を取り出し、台帳（原本）と判断の記録を突き合わせて、ずれの状態を更新する。

bantoはどれが正かを決めない。台帳の値は次のどれかでしか決まらない:
  1. すべての情報源が一致している（出どころ: extracted）
  2. 人の判断（DEC）で決めた
  3. 人が台帳MDを直接書き換えた（Gitに履歴が残る）
  4. 実行結果のように、その属性の正本と定めた種類の情報源（authority）の値
ずれの状態: open（未判断）→ decided（判断済み・実物の直し待ち）→ resolved（一致した）
"""
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from . import decisions as D, ledger as LG
from .domains import DOMAINS
from .model import Source, Fact
from .state import State, key as K, split
from . import fio

SEV_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Drift:
    key: str
    id: str
    domain: object
    container: str
    item: str
    attr: object
    status: str
    L: object
    facts: list                  # [(Source, Fact)]
    deviating: list              # 台帳（なければ多数派）と違う情報源のID
    allowed: dict
    group: str
    group_label: str
    severity: str
    decision: str = ""
    review: dict = field(default_factory=dict)
    target: object = None        # 直し待ちのとき、実物が合わせるべき値（ふつうは台帳の値）


@dataclass
class Result:
    project: str
    base: str
    state: State
    sources: dict                # domain -> [Source]
    ledgers: dict                # domain -> {name: LContainer}
    drifts: list
    errors: list
    decisions: list


def load_config(project):
    p = os.path.join(project, "banto", "sources.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"{p} がありません。情報源の一覧を書いてください（tools/README.md 参照）")
    cfg = json.loads(fio.read(p))
    return cfg.get("domains") or {k: v for k, v in cfg.items() if k in DOMAINS}


def extract_all(project):
    out = {}
    for dname, entries in load_config(project).items():
        mod = DOMAINS[dname]
        srcs = []
        for e in entries:
            s = Source(e["id"], e.get("label", e["id"]), e["kind"], e["path"], dname, e.get("scope_note", ""),
                       e.get("existence", True))
            mod.extract(s, e, project)
            srcs.append(s)
        out[dname] = srcs
    return out


class _Domain:
    """1つの領域の、事実・台帳・許容差への問い合わせをまとめたもの。"""

    def __init__(self, dom, srcs, ledger, state):
        self.dom, self.srcs, self.ledger, self.state = dom, srcs, ledger, state
        self.exist_srcs = [s for s in srcs if s.existence]

    def attr(self, a):
        return self.dom.attr(a)

    def facts(self, c, i, a):
        out = []
        if a == "exists":
            for s in self.exist_srcs:
                if i is None:
                    sc = s.containers.get(c)
                    out.append((s, Fact(sc is not None, "あり" if sc else "記載なし", sc.loc if sc else s.path)))
                elif c in s.containers:
                    it = s.containers[c].items.get(i)
                    out.append((s, Fact(it is not None, "あり" if it else "記載なし",
                                        it.loc if it else s.containers[c].loc)))
            return out
        for s in self.srcs:
            sc = s.containers.get(c)
            if not sc:
                continue
            obj = sc if i is None else sc.items.get(i)
            if obj is not None and a in obj.attrs:
                out.append((s, obj.attrs[a]))
        return out

    def get_L(self, c, i, a):
        lc = self.ledger.get(c)
        if lc is None:
            return None
        if i is None:
            return lc.exists if a == "exists" else lc.attrs.get(a)
        it = lc.items.get(i)
        if it is None:
            return None
        return it.exists if a == "exists" else it.values.get(a)

    def ensure(self, c, i=None):
        """台帳に場所を用意する。新しく作るときは「有無が未定」で作り、有無は判定・判断で確定させる。"""
        lc = self.ledger.get(c)
        if lc is None:
            lc = self.ledger[c] = LG.LContainer(self.state.container_id(self.dom.name, self.dom.container_prefix, c), c,
                                               status="pending")
        if i is None:
            return lc
        it = lc.items.get(i)
        if it is None:
            it = lc.items[i] = LG.LItem(self.state.item_id(self.dom.name, self.dom.item_prefix, c, i), i, exists=None)
        return it

    def set_L(self, c, i, a, v):
        if a == "exists":
            if i is None:
                lc = self.ensure(c)
                lc.status = ("draft" if lc.status in ("removing", "removed", "pending") else lc.status) if v else "removing"
            else:
                self.ensure(c, i).exists = bool(v)
            return
        if i is None:
            self.ensure(c).attrs[a] = v
        else:
            self.ensure(c, i).values[a] = v

    def allowed(self, k):
        c = split(k)[1]
        lc = self.ledger.get(c)
        return lc.allowed.get(k, {}) if lc else {}

    def set_allowed(self, k, entries):
        c = split(k)[1]
        lc = self.ensure(c)
        if entries:
            lc.allowed[k] = entries
        else:
            lc.allowed.pop(k, None)


def _same(a, b):
    return repr(a) == repr(b)


def sync(project, write=True, extra_decisions=None):
    from . import writer, reviews
    base = os.path.join(project, "banto")
    state = State(base)
    sources = extract_all(project)
    ledgers = {d: LG.load_all(base, DOMAINS[d].DOMAIN) for d in sources}
    doms = {d: _Domain(DOMAINS[d].DOMAIN, sources[d], ledgers[d], state) for d in sources}
    errors = []

    # レビュー指摘（取り込み済み）を登録簿に載せる
    review_items = reviews.load(base)
    for r in review_items:
        k = f"review|{r['doc']}|{r['no']}|review"
        if k not in state.drifts:
            state.drifts[k] = {"id": state.drift_id(), "status": "open"}

    # 1. まだ台帳に反映していない判断を、古い順に反映する
    decs = D.load_all(base)
    by_id = state.by_drift_id()
    by_target = state.by_target_id()
    for dec in decs:
        if dec.id in state.applied:
            continue
        try:
            _apply_decision(dec, doms, state, by_id, by_target)
            state.applied.append(dec.id)
        except Exception as e:  # 判断の書き方の誤りは、他を止めずに報告する
            errors.append(f"{dec.id}: {e}")

    # 2. すべての対象について、事実・台帳・許容差を照らし合わせる
    drifts = []
    for dname, X in doms.items():
        dom = X.dom
        names = list(X.ledger.keys())
        for s in X.exist_srcs:
            for c in s.containers:
                if c not in names:
                    names.append(c)
        for c in names:
            ce = _evaluate(X, c, None, "exists", state)
            if ce:
                drifts.append(ce)
            if X.get_L(c, None, "exists") is False and not any(c in s.containers for s in X.exist_srcs):
                X.ledger[c].status, X.ledger[c].items = "removed", {}
                continue
            for a in dom.container_attrs():
                d = _evaluate(X, c, None, a.name, state)
                if d:
                    drifts.append(d)
            inames = list(X.ledger[c].items.keys()) if c in X.ledger else []
            for s in X.exist_srcs:
                for i in (s.containers[c].items if c in s.containers else {}):
                    if i not in inames:
                        inames.append(i)
            for i in inames:
                ie = _evaluate(X, c, i, "exists", state)
                if ie:
                    drifts.append(ie)
                if X.get_L(c, i, "exists") is False and not any(
                        c in s.containers and i in s.containers[c].items for s in X.exist_srcs):
                    X.ledger[c].items.pop(i, None)
                    continue
                for a in dom.item_attrs():
                    d = _evaluate(X, c, i, a.name, state)
                    if d:
                        drifts.append(d)
            if c in X.ledger:
                lc = X.ledger[c]
                if lc.status not in ("removing", "removed", "pending"):
                    lc.status = "draft" if any(d.container == c and d.domain is dom and d.status != "resolved"
                                               for d in drifts) else "confirmed"

    # 3. レビュー指摘
    for r in review_items:
        k = f"review|{r['doc']}|{r['no']}|review"
        e = state.drifts[k]
        drifts.append(Drift(k, e["id"], None, r["doc"], str(r["no"]), None, e["status"], None, [], [], {},
                            "review", "レビュー指摘", "high" if r.get("severity") in ("高", "high") else "medium",
                            e.get("decision", ""), r))

    # 新しく見つかったずれに、重要度・グループの順で番号を振る（以後は変わらない）
    rank = {n: i for i, n in enumerate(DOMAINS)}
    fresh = sorted((d for d in drifts if d.id is None),
                   key=lambda d: (SEV_RANK[d.severity], rank.get(d.domain.name, 9), d.group, d.container, d.item or "", d.attr.name))
    for d in fresh:
        d.id = state.drifts[d.key]["id"] = state.drift_id()
    drifts.sort(key=lambda d: (int(d.id.split("-")[1])))
    res = Result(project, base, state, sources, ledgers, drifts, errors, decs)
    if write:
        writer.write_all(res)
        state.save()
    return res


def _apply_decision(dec, doms, state, by_id, by_target):
    if dec.action not in D.ACTIONS:
        raise ValueError(f"action が不明: {dec.action}")
    if dec.action in ("set", "allow"):
        if not dec.drifts:
            raise ValueError("対象のずれ（drifts）がない")
        for did in dec.drifts:
            k = by_id.get(did)
            if not k:
                raise ValueError(f"{did} は登録されていない")
            dname, c, i, a = split(k)
            if dname == "review":
                raise ValueError(f"{did} はレビュー指摘。accept / reject / answer で判断する")
            X = doms[dname]
            spec = X.attr(a)
            v = spec.parse(dec.value) if dec.value != "" else X.get_L(c, i, a)
            if v is None:
                raise ValueError(f"{did}: 台帳の値が未定のため、value を指定する必要がある")
            X.set_L(c, i, a, v)
            if dec.action == "set":
                X.set_allowed(k, {})
            else:
                X.set_allowed(k, {s.id: (f.value, dec.id) for s, f in X.facts(c, i, a) if not _same(f.value, v)})
            e = state.drifts.setdefault(k, {"id": state.drift_id(), "status": "open"})
            e.update(status="decided", decision=dec.id, value=spec.show(v))
        return
    for did in dec.drifts:
        k = by_id.get(did)
        if not k or not k.startswith("review|"):
            raise ValueError(f"{did} はレビュー指摘ではない")
        state.drifts[k].update(status="resolved", decision=dec.id)
    if dec.action == "accept" and dec.target and dec.attr:
        t = by_target.get(dec.target)
        if not t:
            raise ValueError(f"target {dec.target} が台帳にない")
        dname, c, i = t
        X = doms[dname]
        spec = X.attr(dec.attr)
        v = spec.parse(dec.value)
        X.set_L(c, i, dec.attr, v)
        X.set_allowed(K(dname, c, i, dec.attr), {})
        k = K(dname, c, i, dec.attr)
        e = state.drifts.setdefault(k, {"id": state.drift_id(), "status": "open"})
        e.update(status="decided", decision=dec.id, value=spec.show(v))


def _evaluate(X, c, i, a, state):
    spec = X.attr(a)
    k = K(X.dom.name, c, i, a)
    F = X.facts(c, i, a)
    L = X.get_L(c, i, a)
    if spec.authority:
        auth = [f for s, f in F if s.kind == spec.authority]
        if auth and not _same(L, auth[0].value):
            L = auth[0].value
            X.set_L(c, i, a, L)
    distinct = []
    for _, f in F:
        if not any(_same(f.value, x) for x in distinct):
            distinct.append(f.value)
    if L is None and len(distinct) == 1:
        L = distinct[0]
        X.set_L(c, i, a, L)
    if L is None and not distinct:
        return None
    allowed = X.allowed(k)
    if L is None:
        cnt = Counter(repr(f.value) for _, f in F)
        top = max(cnt.items(), key=lambda kv: (kv[1], kv[0]))[0]
        dev = [s.id for s, f in F if repr(f.value) != top]
    else:
        dev = [s.id for s, f in F if not _same(f.value, L)
               and not (s.id in allowed and _same(allowed[s.id][0], f.value))]
        # 許容差のうち、もう差がなくなったもの・情報源がなくなったものは片付ける
        if allowed:
            live = {s.id: f.value for s, f in F}
            keep = {sid: v for sid, v in allowed.items() if sid in live and not _same(live[sid], L)}
            if keep != allowed:
                X.set_allowed(k, keep)
                allowed = keep
    e = state.drifts.get(k)
    target = L
    if spec.authority and e and e.get("status") == "decided" and L is not None and e.get("value") != spec.show(L):
        # 正本（実行結果）と違う値に決めた：実行結果がその値になるまで直し待ち
        target = spec.parse(e["value"])
        dev = [s.id for s, f in F if not _same(f.value, target)]
        if not dev:
            target = L
    if L is None or dev:
        if e and e["status"] == "decided" and L is not None and e.get("value") == spec.show(target):
            status = "decided"
        else:
            if not e:
                e = state.drifts[k] = {"id": None}   # 番号は、新しいずれをまとめて重要度順に振る
            if e.get("decision") and e.get("status") in ("resolved", "decided"):
                # 判断どおりだったものが、その後また食い違った。以前の判断は経緯として残す
                prev = e.setdefault("previous", [])
                if e["decision"] not in prev:
                    prev.append(e["decision"])
                e.pop("decision", None)
                e.pop("value", None)
            e["status"] = status = "open"
    else:
        if not e:
            return None
        if e["status"] != "resolved":
            e["status"] = "resolved"
        status = "resolved"
    label = {s.id: s.label for s in X.srcs}
    dev_sorted = [s.id for s, _ in F if s.id in dev]
    dvals = sorted({str(f.value) for s, f in F if s.id in dev})
    scope = "c" if i is None else "i"
    group = f"{X.dom.name};{a};{scope};{'+'.join(dev_sorted)};{'+'.join(dvals)};{'台帳' if L is not None else '多数'}"
    who = "・".join(label[x] for x in dev_sorted)
    if a == "exists":
        what = X.dom.container_label if i is None else X.dom.item_label
        has = [f.value for s, f in F if s.id in dev]
        gl = f"{what}が {who} に{'だけ有る' if has and all(has) else '無い'}"
    else:
        gl = f"{spec.label}：{who} が{'台帳' if L is not None else '他'}と異なる"
    if status != "resolved":
        e.update(group=group, group_label=gl, severity=spec.severity)
    return Drift(k, e["id"], X.dom, c, i, spec, status, L, F, dev, allowed, group, gl, spec.severity,
                 e.get("decision", ""), target=target)
