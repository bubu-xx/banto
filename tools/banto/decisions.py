"""判断の記録（banto/decisions/DEC-xxxx.md）の読み書き。

判断はbantoではなく人が行う。ここは、人の判断を決まった形で残し、台帳に反映するための入口。
action:
  set     … 値を正として決める（台帳をその値にし、違う情報源は直す対象になる）
  allow   … 意図した違いとして許容する（台帳の値は value、違う情報源はそのまま許容）
  accept  … レビュー指摘を受け入れる（target・attr・value があれば台帳を直す）
  reject  … レビュー指摘を受け入れない
  answer  … レビュー指摘（質問）に回答する
"""
import datetime
import os
from dataclasses import dataclass, field
from . import frontmatter
from . import fio, frontmatter

ACTIONS = ("set", "allow", "accept", "reject", "answer")


@dataclass
class Decision:
    id: str
    drifts: list
    action: str
    value: str = ""
    target: str = ""
    attr: str = ""
    rule: str = ""
    decided_by: str = ""
    decided_at: str = ""
    reason: str = ""
    path: str = ""
    extra: dict = field(default_factory=dict)


def load_all(base):
    d = os.path.join(base, "decisions")
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not (f.startswith("DEC-") and f.endswith(".md")):
            continue
        p = os.path.join(d, f)
        meta, body = frontmatter.load(fio.read(p))
        reason = body.split("## 理由", 1)[1].strip() if "## 理由" in body else body.strip()
        drifts = meta.get("drifts", [])
        out.append(Decision(meta.get("id", f[:-3]), drifts if isinstance(drifts, list) else [drifts],
                            meta.get("action", ""), meta.get("value", ""), meta.get("target", ""),
                            meta.get("attr", ""), meta.get("rule", ""), meta.get("decided_by", ""),
                            meta.get("decided_at", ""), reason, p))
    out.sort(key=lambda x: int(x.id.split("-")[1]) if x.id.split("-")[-1].isdigit() else 0)
    return out


def write(base, dec, summary=""):
    d = os.path.join(base, "decisions")
    os.makedirs(d, exist_ok=True)
    meta = {"id": dec.id, "drifts": dec.drifts, "action": dec.action}
    for k in ("value", "target", "attr", "rule"):
        if getattr(dec, k):
            meta[k] = getattr(dec, k)
    meta["decided_by"] = dec.decided_by
    meta["decided_at"] = dec.decided_at or datetime.date.today().isoformat()
    body = [f"# {dec.id}", ""]
    if summary:
        body += [summary, ""]
    body += ["## 理由", "", dec.reason.strip() or "（記載なし）", ""]
    p = os.path.join(d, f"{dec.id}.md")
    fio.write(p, frontmatter.dump(meta) + "\n" + "\n".join(body))
    return p
