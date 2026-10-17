# banto

> 帳簿はすべて頭に入っている。合わないところを見つけたら、両方の言い分と経緯を揃えて差し出す。決めるのは、あなた。

banto（番頭）は、システム開発の成果物（要件・設計・DB定義・コード・テスト）の関係をMDの台帳で管理し、
中身がずれたときに「何をどう直すか」を人が判断するための材料（判断票）を揃える仕組みです。Claude Code のプラグイン（Skill・エージェント）と、Pythonのスクリプトでできています。

- **台帳（MD）が原本**：テーブル・列・テストのつながりと値を、IDつきのMDで持つ
- **ずれは判断票に**：設計書・DDL・ORM・テスト・実行結果を突き合わせ、食い違いを1件ずつ「何が・どこで・なぜ・どう直せるか」の形で出す
- **決めるのは人**：bantoはどれが正かを決めない。判断と理由を記録し、次の判断の材料にする
- **提出はExcelで**：台帳から設計書・テスト仕様書をExcelに清書し、レビュー表で指摘を受けて往復する

```
 既存の設計書・DDL・ORM・テスト・実行結果
              │ 取り込み・同期（スクリプト：毎回同じ結果）
              ▼
   台帳（MD・原本） ──── 食い違い ───▶ 判断票 ──▶ 人が判断 ──▶ 判断の記録（DEC）
              ▲                                                     │
              │ 同期で一致を確認                                     ▼
          実物を直す ◀────────────── 直し待ちリスト ◀──────── 台帳に反映
              │
              └──▶ Excel清書 ＋ レビュー表 ──▶ 指摘を取り込み ──▶ 判断票
```

## 入れ方

Claude Code のプラグインとして：

```
/plugin marketplace add bubu-xx/banto
/plugin install banto@banto
```

必要なもの：Python 3.10 以上、openpyxl（`pip install openpyxl`）。

## 使い方

対象プロジェクトで Claude Code に話しかけるか、Skill を呼ぶ。

| やりたいこと | Skill |
|---|---|
| 既存プロジェクトを取り込む（初回） | `/banto:import` |
| 変更のあと、ずれを確かめる | `/banto:check-drift` |
| 判断票を見て判断する | `/banto:decision-sheet` |
| 判断を記録して実物を直す | `/banto:apply-decision` |
| Excelとレビュー表を出す | `/banto:export-excel` |
| 記入済みのレビュー表を取り込む | `/banto:import-review` |

役割を分けたエージェント（`extractor` 抽出係、`matcher` 照合係、`applier` 反映係、`auditor` 監査係）が、Skillの中で使われます。どの係も「どれが正か」は決めません。

### コマンドだけで使う

```
python3 scripts/banto.py --project <対象プロジェクト> sync
python3 scripts/banto.py --project <対象> decide DRF-0017 --set 10 --by 名前 --reason "10桁に統一"
python3 scripts/banto.py --project <対象> decide --group "<グループ>" --allow --by 名前 --reason "方言差"
python3 scripts/banto.py --project <対象> check --strict
python3 scripts/banto.py --project <対象> export
python3 scripts/banto.py --project <対象> import-review review-RV001.xlsx
```

情報源の一覧（`banto/sources.json`）の書き方と、台帳・判断票・判断の記録の形式は [docs/spec.md](docs/spec.md)。

## 文書

- [docs/concept.md](docs/concept.md) — 構想（なぜ、何を、どう分担するか）
- [docs/spec.md](docs/spec.md) — 規約（ファイルの形、IDの体系、値の書き方）
- [tools/README.md](tools/README.md) — スクリプトの構成と開発

## 状態

v0.1。対象はテーブル定義（MD・Excel設計書、DDL〔H2・MySQL・PostgreSQL〕、JPA）とテスト（MDの仕様書・報告書、JUnit 5、surefire）。

テスト：`python3 -m unittest discover -s tests`
