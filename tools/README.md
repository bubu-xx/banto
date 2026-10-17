# tools

bantoのスクリプト群。事実を確定させる処理（抽出・照合・出力）だけを受け持ち、どれが正かは決めない。

## import-tables

```
cd tools
python -m banto import-tables <対象プロジェクトのパス>
```

対象プロジェクトの `banto/sources.json` に情報源を列挙しておく。対応する情報源の種類:

| kind | 内容 |
|---|---|
| `xlsx` | Excel設計書の「テーブル: 名前」＋「カラム / 型 / 制約」表（`sheet` を指定） |
| `md` | MD設計書の見出し（`テーブル名`）直下の「カラム / 型 / 制約」表 |
| `ddl` | CREATE TABLE / ALTER TABLE / CREATE INDEX（`dialect`: h2・mysql・postgres） |
| `jpa` | JPAエンティティ（Java）の注釈 |

出力（対象プロジェクトの `banto/` 配下）:

- `extracted/tables.json` — 取り出した事実
- `design/detail/tables/*.md` — テーブル定義（一致した部分と、未判断のずれへの参照）
- `drifts/DRF-*.md` — 判断票
- `drifts/README.md` — ずれの一覧（グループ別）

必要なもの: Python 3.10以上、openpyxl。

### 既知の限界

- JPAは注釈だけを読む。Validatorクラスなどのコードで実装された必須チェックは拾わない
- MySQLの大文字小文字の区別は照合順序で決まるため、DDLの表記からは判定しない
- 再実行でずれの件数が減ると、古い判断票ファイルが残る
