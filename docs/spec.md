# banto 規約（たたき台）

構想（[concept.md](concept.md)）を動かすための規約の案。実際に一周回してから確定する。

## 1. 配置（対象プロジェクト内）

```
banto/
  requirements/      要件
  design/basic/      基本設計
  design/detail/     詳細設計（テーブル定義を含む）
  tests/             テスト仕様と結果
  decisions/         判断の記録
  drifts/            未判断のずれ（判断票）
  export/            Excel出力（生成物。直接編集しない）
```

## 2. frontmatter

```yaml
---
doc_id: DD-TBL-001        # 文書ID
title: テーブル定義書
kind: requirements | basic-design | detail-design | test-spec | test-result
version: 1.0
status: draft | confirmed
---
```

`status: confirmed` は「この文書に未判断のずれが無い」状態。ずれが1件でも残っていれば `draft`。

## 3. ID体系

| 接頭辞 | 対象 |
|---|---|
| `REQ-` | 要件 |
| `BD-` | 基本設計の項目 |
| `DD-` | 詳細設計の項目 |
| `TBL-` / `COL-` | テーブル / 列 |
| `API-` | API |
| `TC-` | テストケース |
| `DEC-` | 判断の記録 |
| `DRF-` | ずれ（判断票） |

- IDは一度振ったら変えない。削除しても番号は再利用しない
- 各項目は上流のIDを `from:` で持つ（例：`DD-012` は `from: [BD-004]`）

### 実物とのつなぎ方（案。未決）

- **案A**：MD側に `impl:`（ファイルパスとシンボル）を持ち、コードには手を入れない
- **案B**：コード側のコメントやテスト名にIDを書く（例：テスト名に `TC-031` を含める）

テストは案B（テスト名にTC-ID）、それ以外は案A、という組み合わせが有力。

## 4. 出どころタグ

MDの各項目に、その内容がどこから来たかを持たせる。

| タグ | 意味 |
|---|---|
| `extracted` | 実物（DB、コード、テスト）からスクリプトで抽出した |
| `inferred` | AIが推定した。人の確認が必要 |
| `confirmed` | 人が確認した（判断の記録 `DEC-` を伴う） |

あわせて `source:`（どの情報源か）を持つ。

## 5. ずれの分類

| 分類 | 意味 |
|---|---|
| `match` | 一致 |
| `only-a` / `only-b` | 片方にしかない |
| `conflict` | 両方にあるが内容が違う |

## 6. 判断票（`drifts/DRF-xxxx.md`）

```markdown
---
id: DRF-0001
kind: conflict
targets: [COL-0123]
severity: high | medium | low
group: <同じ原因のずれをまとめるキー>
status: open | decided
---
## 何がずれているか
| 情報源 | 内容 |
|---|---|
| 既存Excel設計書 | VARCHAR(50) |
| DB | VARCHAR(100) |

## つながり
- 上流: BD-004
- 下流: TC-031, src/order/repository.py#save

## 経緯
- 2024-03 マイグレーション 0042 で100に変更（コミット abc123）
- 設計書は2023-11版のまま

## 選択肢と影響
- A. MDをDBに合わせる → 設計書の改版のみ
- B. DBを50に戻す → マイグレーション追加、TC-031の修正
```

## 7. 判断の記録（`decisions/DEC-xxxx.md`）

```markdown
---
id: DEC-0001
drifts: [DRF-0001]          # 一括判断なら複数
rule: <一括判断の規則。個別なら空>
decision: A
decided_by: <名前>
decided_at: 2026-10-17
---
## 理由
<なぜそう決めたか>
```

## 8. レビュー表の列

指摘No／対象文書・版／箇所（ID、シート・行）／指摘内容／種別（誤り・漏れ・表現・質問）／重要度／対応方針／対応内容／反映版／確認者／ステータス

取り込んだ指摘は `DRF-` として判断票の流れに乗せる。
