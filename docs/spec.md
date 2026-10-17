# banto 規約（v0.2）

[concept.md](concept.md) の考え方を、ファイルの形として決めたもの。流れは [flow.md](flow.md)。実装はこの規約どおりに動く。

## 1. 対象プロジェクトに置くもの

```
banto/
  project.json               案件の設定（名前、関係者と役割、AIの扱い、様式、人が書く列、型名）
  sources.json               情報源の一覧（人が書く）
  manual/                    人が書く節・表（様式の項目ごと）
  coverage/                  網羅表 README.md と、不足票・不要の候補の確認票
  format/<様式名>/           専用様式（template.xlsx・structure.json・layout.json・mapping.json・format.json）
  releases/<文書>-v<版>/     提出版（Excel・RELEASE.md・snapshot.json）
  design/detail/tables/      台帳：テーブル定義（テーブルごとに1ファイル + README.md）
  tests/                     台帳：テスト（テストクラスごとに1ファイル + README.md）
  drifts/                    判断票 DRF-xxxx.md、一覧 README.md、直し待ち APPLY.md
  decisions/                 判断の記録 DEC-xxxx.md
  reviews/                   取り込んだレビュー指摘 RVxxx.json
  state/                     機械用の状態（ids.json / drifts.json / applied.json / versions.json）
  export/                    Excel出力（写し。直接編集しない）
```

`state/` も含めてGitで管理する。IDの採番とずれの状態は、ここにしか残らない。

## 2. 情報源の一覧（sources.json）

```json
{
  "domains": {
    "tables": [
      {"id": "design-md", "label": "既存MD設計書", "kind": "md", "path": "docs/design.md", "dialect": "h2",
       "scope_note": "Owner ドメイン中心（設計書自身の記載）"},
      {"id": "ddl-h2", "label": "DDL（H2）", "kind": "ddl", "path": "src/main/resources/db/h2/schema.sql", "dialect": "h2"}
    ],
    "tests": [
      {"id": "test-spec", "label": "テスト仕様書", "kind": "md", "path": "docs/test-spec.md",
       "columns": {"種別": "category", "検証内容": "purpose"}},
      {"id": "surefire", "label": "実行結果", "kind": "surefire", "path": "target/surefire-reports"}
    ]
  }
}
```

| 領域 | kind | 読むもの |
|---|---|---|
| tables | `md` | 見出し（`` `テーブル名` ``）直下の「カラム / 型 / 制約」表 |
| tables | `xlsx` | 「テーブル: 名前」行に続く「カラム / 型 / 制約」表（`sheet` を指定） |
| tables | `ddl` | CREATE TABLE / ALTER TABLE / CREATE INDEX（`dialect`: `h2` `mysql` `postgres`） |
| tables | `jpa` | JPAエンティティの注釈（`@Table` `@Column` `@Id` `@ManyToOne` `@JoinTable` `@NotBlank` `@Size` `@Pattern` など） |
| tests | `md` | 見出しに `` `クラス名.java` ``、その下の「テストメソッド」表。列の対応は `columns`（`category` `purpose` `precondition` `steps` `expected` `result`） |
| tests | `junit` | JUnit 5 の `@Test` 等のメソッド。`@Nested` の内側は `内側クラス#メソッド` |
| tests | `surefire` | `TEST-*.xml` の実行結果。有無の比較には参加しない |

- `scope_note`：情報源が自ら述べている対象範囲。有無のずれの判断票に「経緯」として出る
- `comment_as`（ddl）：DBのコメントを `logical_name`（論理名、既定）と `description`（説明）のどちらとして読むか
- `sections`（tests の md）：クラスの節の小見出しの本文を、コンテナの属性として読む（例：`{"目的": "summary"}`）
- `existence: false`：有無の比較に参加させない（実行結果のように、存在を表さない情報源）

## 2.5 案件の設定（project.json）

```json
{
  "system": "PetClinic", "project": "保守開発", "customer": "",
  "format": "standard",
  "people": [{"name": "油山", "roles": ["judge", "approver", "author"]}],
  "ai_policy": {"code_access": "許可（契約書 第12条で確認）", "note": ""},
  "extra_columns": {"tables": ["区分"]},
  "type_names": {"string": "VARCHAR", "integer": "INTEGER", "date": "DATE", "decimal": "DECIMAL"}
}
```

- `format`：`standard`（標準様式）か `custom:<様式名>`（専用様式）
- `people.roles`：`judge`（判断者）・`approver`（承認者）・`author`（作成者）。登録があれば `decide` は判断者、`release` は承認者だけが実行できる
- `extra_columns`：様式が求める、bantoに無い「人が書く列」（領域ごと）。専用様式の対応づけを確定すると足される
- `type_names`：台帳の型（`string` など）を、設計書に載せるときの型名

`banto init` でひな形ができる。

## 3. 台帳（原本）

1コンテナ（テーブル、テストクラス）につき1ファイル。人が直接読み書きでき、スクリプトも読み戻す。

```markdown
---
doc_id: TBL-001
title: テーブル owners
domain: tables
container: owners
status: draft
---

# owners

<!-- banto:attrs -->
| 属性 | 値 |
|---|---|
| 一意制約 | （なし） |

<!-- banto:items -->
| ID | 列 | 型 | 長さ | NULL | PK | FK | INDEX | 自動採番 | 大小区別 | 符号なし | 状態 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| COL-006 | `telephone` | string | 20 ⚠[DRF-0017](../../../drifts/DRF-0017.md) | ... | ⚠ 未判断あり |

<!-- banto:allowed -->
## 許容された差
| 対象 | 属性 | 情報源 | 許容する値 | 判断 |

## 実物の場所

## メモ
<!-- banto:notes -->
（ここから下は自由に書いてよい。同期しても残る）
```

- `<!-- banto:... -->` の直後の表を機械が読む。印は消さない
- `⚠[DRF-…](…)`（未判断）・`⏳[DRF-…](…)`（直し待ち）は bantoが付ける印で、読み戻すときは無視される
- `status`：`confirmed`（未判断・直し待ちなし）／`draft`／`pending`（有無が未判断）／`removing`（削除予定）／`removed`
- 「状態」列：`✓ 一致`（判断で決めた値があれば `✓ 一致（DEC-0003）`）、`⚠ 未判断あり`、`⏳ 直し待ちあり`、`許容差あり`、`有無未定`、`削除予定`
- テスト台帳の「対象」列は人が書く列。検証している列のIDを書く（推定なら `COL-006（推定）`）。`banto check` がIDの実在を確かめる

### 項目（v0.2）

| 領域 | 項目（列）の属性 | コンテナの属性 |
|---|---|---|
| テーブル | 論理名・型・長さ・小数桁・NULL・初期値・PK・FK・INDEX・自動採番・大小区別・符号なし・説明 | 論理名・説明・種別・想定件数・一意制約・複合インデックス |
| テスト | 種別・検証内容・前提条件・手順・期待結果・結果（＋人が書く列「対象」） | テストレベル・目的 |

論理名・説明・前提条件などは、情報源にあれば取り込み、無ければ人が台帳に書く（情報源が表していない値は比較しないので、人が書いた値とずれにならない）。
DDLの `COMMENT` は sources.json の `comment_as`（`logical_name`／`description`）で行き先を決める。設計書の表は見出しで列の意味を判断する（列名・論理名・型・桁数・NOT NULL・PK・初期値・備考など）。

### 値の書き方

| 属性 | 書き方 |
|---|---|
| 型 | `integer` `string` `date` など |
| 長さ | 数値、または `無制限` |
| NULL | `NULL`（許容）／`NOT NULL` |
| PK・INDEX・自動採番・符号なし | `○`／`×` |
| FK | `テーブル.列`、なしは `×` |
| 大小区別 | `区別する`／`区別しない` |
| 結果 | `pass` `fail` `error` `skipped` |
| （共通） | `—` はどの情報源も表していない、`?` は未定（判断待ち） |

## 4. ID

| 接頭辞 | 対象 |
|---|---|
| `TBL-` / `COL-` | テーブル / 列 |
| `TSU-` / `TC-` | テストクラス / テストケース |
| `DRF-` | ずれ（判断票） |
| `DEC-` | 判断の記録 |
| `RV` | レビュー表（`RV001` …） |

一度振ったIDは変えず、再利用しない。採番表は `state/ids.json`。新しいずれの番号は、見つかった時点で重要度・グループ順に振る。

## 5. 台帳の値がどう決まるか

台帳の値は、次のどれかでしか決まらない。bantoが多数決で決めることはない。

1. すべての情報源が一致している
2. 人の判断（DEC）
3. 人が台帳MDを直接書き換えた（Gitに履歴が残る）
4. 「正本の種類」が決まっている属性は、その情報源の値（v0.1 ではテストの「結果」＝ surefire の実行結果）

## 6. ずれ

- 種類：`only-in`（有無）、`conflict`（値）、`review`（レビュー指摘）
- 状態：`open`（未判断）→ `decided`（判断済み・実物の直し待ち）→ `resolved`（一致した）。解決済みのものが再び食い違うと、同じ番号で `open` に戻り、以前の判断が経緯に残る
- 重要度：属性ごとに既定（型・NULL・PK・FK・有無は高、長さ・大小区別は中、INDEX・自動採番・符号なし・一意制約は低）
- グループ：`領域;属性;c|i;違う情報源;違う値;台帳|多数`。同じグループは同じ規則でまとめて判断できる候補（`banto decide --group "<グループ>"`）

## 7. 判断票（drifts/DRF-xxxx.md）

frontmatter（`id` `domain` `kind` `target` `attribute` `severity` `group` `status` `decision`）と、次の節からなる。

1. 何がずれているか（台帳と各情報源の値・書かれ方・場所、台帳との差）
2. つながり（台帳、上流、実物、下流のテスト）
3. 経緯（設計書の注意書き、変更履歴、対象範囲、許容済みの差、以前の判断）
4. 選択肢と影響（値ごとの「直す必要がある情報源」と、そのコマンド）
5. 判断
6. 補足（`<!-- banto:notes -->` より下。人や照合係の分析。同期しても残る）

## 8. 判断の記録（decisions/DEC-xxxx.md）

```markdown
---
id: DEC-0002
drifts: [DRF-0017]
action: set
value: 10
rule: ""
decided_by: 油山
decided_at: 2026-10-17
---
# DEC-0002

## 理由
10桁固定に統一する
```

| action | 意味 |
|---|---|
| `set` | 値を正とする。台帳をその値にし、違う情報源は直し待ちになる |
| `allow` | 意図した違いとして許容する。台帳の値は `value`（省略時は今の台帳の値）、違う情報源は許容差として台帳に記録 |
| `accept` | レビュー指摘を受け入れる。`target`・`attr`・`value` があれば台帳を直す |
| `reject` / `answer` | レビュー指摘を受け入れない／回答する |
| `exclude` / `include` | 様式の項目（`target`）を、このシステムには不要／必要と判断する |

判断の記録は `banto decide` で作る。適用済みの判断は `state/applied.json` に残り、二度は適用されない。

## 9. Excelとレビュー表（banto export / import-review）

- 標準様式：文書ごとに1冊（`BD_基本設計書.xlsx` `DD_詳細設計書.xlsx` `TD_テーブル定義書.xlsx` `TS_テスト仕様書.xlsx`）。表紙（project.json の名前・作成者・承認）、改訂履歴、目次（項目ごとに「記載／情報不足／対象外（理由）／不要の候補」）、本体、未判断・情報不足
- 専用様式：確定した配置と対応づけで、様式のExcelに値を入れる
- 本体のシートは保護（パスワードなし）。台帳の行には台帳への対応（`banto-ref`）を非表示列で持つ。型は project.json の `type_names` で設計書の型名にする
- 版は文書の中身が前回の出力から変わったときだけ上がる（`state/versions.json`）。改訂履歴に変更の内容と、反映した判断・判断した人が残る
- レビュー表：指摘No／対象文書／版／箇所（ID）／箇所の補足／指摘内容／種別／重要度／指摘者（ここまで記入）。IDは項目ID（BD-01 など）、テーブル・列・テストのIDのどれでもよい。非表示の `banto` シートにレビューIDと版を持つ
- 取り込んだ指摘は `reviews/RVxxx.json` に保存され、1件ずつ `review` のずれになる

## 9.5 様式と網羅（banto coverage）

様式は「文書 → 項目」の定義（`formats/standard/format.json`、専用様式は `banto/format/<名前>/format.json`）。項目の種類：

| kind | 中身 | 情報の出どころ |
|---|---|---|
| `text` | 文章の節（システム概要など） | `banto/manual/<ID>.md` に人が書く |
| `manual-table` | 人が書く表（画面一覧など）。`columns` と `required` | `banto/manual/<ID>.md` の `<!-- banto:table -->` の下の表 |
| `ledger-list` | 台帳のコンテナの一覧（テーブル一覧など） | 台帳 |
| `ledger-table` | 台帳の定義（テーブル定義など）。`fields`・`required`・`container_fields`・`container_required` | 台帳 |
| `ref` | 別冊を参照 | — |

`signals`（手がかり：`glob` か `grep`＋`files`、`label`）がある項目は、手がかりが見つからなければ「不要の候補」。不要・必要は人が判断する（`banto decide --item <ID> --exclude|--include`、DECの action は `exclude`／`include`）。
長さは文字列・数値型の列だけ、小数桁は数値型の列だけを数える。未判断のずれで空になっている値は「判断待ち」として、情報不足とは別に数える。

## 9.6 提出（banto release）

`banto release <文書ID> --by <承認者> --reason <理由>`。未判断・直し待ち・情報不足・要不要が未判断の項目があれば、`--allow-open` が無い限り提出しない。
提出版は `banto/releases/<文書ID>-v<版>/`（Excel・`RELEASE.md`・`snapshot.json`）に残り、`state/versions.json` に承認者と残課題が記録される。同じ版は二度提出できない。

## 9.7 専用様式（banto format）

| 段階 | コマンド | ファイル |
|---|---|---|
| 構造の読み取りと配置の下書き | `format read <様式.xlsx> --name <名前>` | `structure.json` `STRUCTURE.md` `layout.json` |
| 試し刷り（配置の確認） | `format trial --name <名前>` | `trial-layout.xlsx` |
| 配置の確定 | `format confirm --name <名前> --step layout --by <名前>` | `layout.json`（status: confirmed） |
| 対応づけの下書き | `format map --name <名前> --doc-id <ID> --doc-title <文書名>` | `mapping.json` |
| 試し刷り（値の確認） | `format trial --name <名前> --data` | `trial-data.xlsx` |
| 対応づけの確定 | `format confirm --name <名前> --step mapping --by <名前>` | `mapping.json`・`format.json`、project.json の `extra_columns` |

layout.json：シートごとに `role`（`cover` `history` `per-container` `list` `other`）、`fields`（`label`・`cell`）、`tables`（`header_row`・`first_row`・`last_row`・`columns`）。
mapping.json：欄・列ごとに bantoの値（`project.*` `doc.*` `container.*` `item.*` `item.free:<見出し>` `history.*` `none`）。`per-container` のシートは、テーブルごとに複製して値を入れる。明細が様式の行数を超えたら、1行目の書式を写して続ける。

## 10. 検査（banto check）

判断の記録の誤り・存在しないずれへの参照、台帳と採番表のIDの食い違い・重複、テスト台帳「対象」のIDの実在（IDの鎖）を検査する。`--strict` は未判断・直し待ちが残っていても失敗にする。
