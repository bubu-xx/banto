# banto 規約（v0.1）

[concept.md](concept.md) の考え方を、ファイルの形として決めたもの。v0.1 の実装はこの規約どおりに動く。

## 1. 対象プロジェクトに置くもの

```
banto/
  sources.json               情報源の一覧（人が書く）
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
| tests | `md` | 見出しに `` `クラス名.java` ``、その下の「テストメソッド」表。列の対応は `columns`（結果の列は `result`） |
| tests | `junit` | JUnit 5 の `@Test` 等のメソッド。`@Nested` の内側は `内側クラス#メソッド` |
| tests | `surefire` | `TEST-*.xml` の実行結果。有無の比較には参加しない |

- `scope_note`：情報源が自ら述べている対象範囲。有無のずれの判断票に「経緯」として出る
- `existence: false`：有無の比較に参加させない（実行結果のように、存在を表さない情報源）

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

判断の記録は `banto decide` で作る。適用済みの判断は `state/applied.json` に残り、二度は適用されない。

## 9. Excelとレビュー表（banto export / import-review）

- 領域ごとに1冊（`tables.xlsx` `tests.xlsx`）：表紙、改訂履歴、一覧、本体（コンテナごと）、許容された差、未判断・直し待ち
- 本体のシートは保護（パスワードなし）。各行に台帳への対応（`banto-ref`）を非表示列で持つ
- 版は台帳の中身が前回の出力から変わったときだけ上がる（`state/versions.json`）
- レビュー表：指摘No／対象文書／版／箇所（ID）／箇所の補足／指摘内容／種別／重要度／指摘者（ここまで記入）、対応方針以降はbantoが使う。入力規則つき。非表示の `banto` シートにレビューIDと版を持つ
- 取り込んだ指摘は `reviews/RVxxx.json` に保存され、1件ずつ `review` のずれになる

## 10. 検査（banto check）

判断の記録の誤り・存在しないずれへの参照、台帳と採番表のIDの食い違い・重複、テスト台帳「対象」のIDの実在（IDの鎖）を検査する。`--strict` は未判断・直し待ちが残っていても失敗にする。
