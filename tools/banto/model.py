"""情報源から取り出したテーブル定義の共通の形。

各属性は「その情報源が明示しているときだけ」値を持つ。明示していない属性は None で、
突合せの対象から外す（書かれていないことは、違うことではない）。
"""
from dataclasses import dataclass, field


@dataclass
class Fact:
    value: object          # 正規化した値（比較に使う）
    shown: str             # 判断票に表示する元の書き方
    loc: str               # 場所（ファイル:行 や シート!セル）


@dataclass
class Column:
    name: str
    loc: str
    attrs: dict = field(default_factory=dict)   # 属性名 -> Fact

    def set(self, attr, value, shown, loc=None):
        self.attrs[attr] = Fact(value, shown, loc or self.loc)


@dataclass
class Table:
    name: str
    loc: str
    columns: dict = field(default_factory=dict)  # 列名 -> Column
    unique_keys: list = field(default_factory=list)  # [(列の組, 場所)]

    def col(self, name, loc):
        c = self.columns.get(name)
        if c is None:
            c = self.columns[name] = Column(name, loc)
        return c


@dataclass
class Source:
    id: str
    label: str
    kind: str
    path: str
    tables: dict = field(default_factory=dict)   # テーブル名 -> Table
    scope_note: str = ""                         # 情報源自身が述べている対象範囲

    def table(self, name, loc):
        t = self.tables.get(name)
        if t is None:
            t = self.tables[name] = Table(name, loc)
        return t


# 判断票に出すときの属性の日本語名と、並べ替え・重要度の既定
ATTRS = {
    "base_type": ("型", "high"),
    "nullable": ("NULL可否・必須", "high"),
    "pk": ("主キー", "high"),
    "fk": ("外部キー", "high"),
    "length": ("桁・長さ", "medium"),
    "case_insensitive": ("大文字小文字の区別", "medium"),
    "identity": ("自動採番", "low"),
    "indexed": ("インデックス", "low"),
    "unsigned": ("符号なし", "low"),
}
