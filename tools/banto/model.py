"""情報源から取り出した事実の共通の形。

どの領域（テーブル、テスト…）も「入れ物（コンテナ）」と「項目」の2階層で表す。
  テーブル定義: コンテナ = テーブル、項目 = 列
  テスト      : コンテナ = テストクラス、項目 = テストメソッド
属性は、その情報源が明示しているときだけ値を持つ。書かれていないことは、違うことではない。
"""
from dataclasses import dataclass, field


@dataclass
class Fact:
    value: object   # 正規化した値（比較に使う。str / int / bool）
    shown: str      # 判断票に出す、元の書き方
    loc: str        # 場所（ファイル:行、ファイル!シート!セル）


@dataclass
class Item:
    name: str
    loc: str
    attrs: dict = field(default_factory=dict)

    def set(self, attr, value, shown, loc=None):
        self.attrs[attr] = Fact(value, shown, loc or self.loc)


@dataclass
class Container:
    name: str
    loc: str
    items: dict = field(default_factory=dict)
    attrs: dict = field(default_factory=dict)

    def item(self, name, loc):
        it = self.items.get(name)
        if it is None:
            it = self.items[name] = Item(name, loc)
        return it

    def set(self, attr, value, shown, loc=None):
        self.attrs[attr] = Fact(value, shown, loc or self.loc)


@dataclass
class Source:
    id: str
    label: str
    kind: str
    path: str
    domain: str
    scope_note: str = ""
    existence: bool = True      # 有無の比較に参加するか（実行結果は「実行されたか」しか分からないので False）
    containers: dict = field(default_factory=dict)

    def container(self, name, loc):
        c = self.containers.get(name)
        if c is None:
            c = self.containers[name] = Container(name, loc)
        return c
