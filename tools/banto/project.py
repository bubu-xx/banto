"""案件の設定（banto/project.json）。準備段階で決めることを1か所に持つ。

  system / project / customer … 表紙に出る名前
  format                      … 提出する様式（"standard" か "custom:<名前>"）
  people                      … 関係者と役割（judge 判断者 / approver 承認者 / author 作成者）
  ai_policy                   … AIにコードや文書を読ませてよいか（案件ごとに確認した結果）
  extra_columns               … 様式が求める、案件独自の「人が書く列」（領域ごと）
役割が1人も登録されていなければ、役割の確認はしない（個人での利用を妨げないため）。
"""
import json
import os
from . import fio

ROLES = {"judge": "判断者", "approver": "承認者", "author": "作成者"}

DEFAULT = {
    "system": "",
    "project": "",
    "customer": "",
    "format": "standard",
    "people": [],
    "ai_policy": {"code_access": "未確認", "note": ""},
    "extra_columns": {},
    "type_names": {"string": "VARCHAR", "integer": "INTEGER", "date": "DATE", "decimal": "DECIMAL"},
}


def display(cfg, attr, v):
    """台帳の値を、設計書（Excel）に載せる書き方にする。型は正規化した名前（string など）を、案件の型名に戻す。"""
    if v is None:
        return ""
    if attr.name == "base_type":
        return (cfg or {}).get("type_names", DEFAULT["type_names"]).get(v, str(v).upper())
    return attr.show(v)


def path(base):
    return os.path.join(base, "project.json")


def load(base):
    p = path(base)
    data = json.loads(fio.read(p)) if os.path.exists(p) else {}
    out = json.loads(json.dumps(DEFAULT))
    out.update(data)
    return out


def save(base, data):
    fio.write(path(base), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def people_with(cfg, role):
    return [p["name"] for p in cfg.get("people", []) if role in p.get("roles", [])]


def check_role(cfg, name, role):
    """役割が登録されているのに、その人がその役割を持っていなければ、理由を返す。"""
    if not cfg.get("people"):
        return None
    names = people_with(cfg, role)
    if name not in names:
        who = "、".join(names) or "（登録なし）"
        return f"{name} は{ROLES[role]}として登録されていない（{ROLES[role]}：{who}）。project.json の people を確認してください"
    return None


def first(cfg, role):
    names = people_with(cfg, role)
    return names[0] if names else ""
