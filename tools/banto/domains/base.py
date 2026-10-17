"""領域（テーブル定義・テスト…）ごとの属性の定義と、値の表示・読み戻し。

台帳MDは原本として人が読み書きし、スクリプトも読み戻す。そのため show と parse は互いに逆変換になっている。
"""
from dataclasses import dataclass, field

NONE = "—"


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _unesc(s):
    return s.replace("\\|", "|")


SHOW = {
    "bool": lambda v: "○" if v else "×",
    "nullable": lambda v: "NULL" if v else "NOT NULL",
    "length": lambda v: "無制限" if v == "unbounded" else str(v),
    "ci": lambda v: "区別しない" if v else "区別する",
    "exists": lambda v: "あり" if v else "なし",
    "fk": lambda v: v if v else "×",
    "text": lambda v: _esc(v) if v != "" else "（なし）",
}

PARSE = {
    "bool": {"○": True, "×": False, "true": True, "false": False, "あり": True, "なし": False, "yes": True, "no": False},
    "nullable": {"NULL": True, "NOT NULL": False, "null": True, "not null": False, "NULL許容": True, "必須": False},
    "ci": {"区別しない": True, "区別する": False, "true": True, "false": False},
    "exists": {"あり": True, "なし": False, "true": True, "false": False, "present": True, "absent": False},
}


@dataclass
class Attr:
    name: str
    label: str
    severity: str
    vtype: str = "text"
    scope: str = "item"          # item | container
    authority: str = None        # この種類の情報源の値を常に台帳に採る（例: 実行結果）
    choices: tuple = ()          # text のとき、取りうる値（あれば検証する）

    def show(self, v):
        if v is None:
            return NONE
        return SHOW.get(self.vtype, SHOW["text"])(v)

    def parse(self, text):
        t = (text or "").strip()
        if t in ("", NONE, "?"):
            return None
        if self.vtype in PARSE:
            if t in PARSE[self.vtype]:
                return PARSE[self.vtype][t]
            low = {k.lower(): v for k, v in PARSE[self.vtype].items()}
            if t.lower() in low:
                return low[t.lower()]
            raise ValueError(f"{self.label}の値として読めない: {t}（使える値: {'、'.join(PARSE[self.vtype])}）")
        if self.vtype == "length":
            if t in ("無制限", "unbounded"):
                return "unbounded"
            if t.isdigit():
                return int(t)
            raise ValueError(f"{self.label}の値として読めない: {t}（数値か「無制限」）")
        if self.vtype == "fk":
            return "" if t in ("×", "なし", "none") else t
        if t == "（なし）":
            return ""
        v = _unesc(t)
        if self.choices and v not in self.choices:
            raise ValueError(f"{self.label}の値として読めない: {t}（使える値: {'、'.join(self.choices)}）")
        return v


@dataclass
class Domain:
    name: str
    title: str                   # 文書名（Excelの表紙などに使う）
    container_label: str
    item_label: str
    container_prefix: str
    item_prefix: str
    ledger_dir: str
    exists_severity: str
    attrs: dict = field(default_factory=dict)
    free_columns: tuple = ()     # 台帳にだけある人が書く列（例: テストの「対象」）

    def item_attrs(self):
        return [a for a in self.attrs.values() if a.scope == "item"]

    def container_attrs(self):
        return [a for a in self.attrs.values() if a.scope == "container"]

    def attr(self, name):
        if name == "exists":
            return Attr("exists", "有無", self.exists_severity, "exists")
        return self.attrs[name]
