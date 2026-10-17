# banto

> 帳簿はすべて頭に入っている。合わないところを見つけたら、両方の言い分と経緯を揃えて差し出す。決めるのは、あなた。

banto（番頭）は、システム開発の成果物（要件・設計・DB定義・コード・テスト）の関係をMDの台帳で管理し、
中身がずれたときに「何をどう直すか」を人が判断するための材料（判断票）を揃える仕組みです。Claude Code のプラグイン（Skill・エージェント）と、Pythonのスクリプトでできています。

- **台帳（MD）が原本**：テーブル・列・テストのつながりと値を、IDつきのMDで持つ
- **ずれは判断票に**：設計書・DDL・ORM・テスト・実行結果を突き合わせ、食い違いを1件ずつ「何が・どこで・なぜ・どう直せるか」の形で出す
- **決めるのは人**：bantoはどれが正かを決めない。判断と理由を記録し、次の判断の材料にする
- **設計書を作れる状態かが分かる**：様式（標準または顧客の専用様式）の項目ごとに、情報が揃っているか、足りないか、不要の候補かを網羅表にする
- **提出はExcelで**：台帳から様式どおりのExcelを清書し、レビュー表で指摘を受けて往復し、承認者が版を確定する

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

案件の流れに沿って、Skill を順に使う（流れの全体は [docs/flow.md](docs/flow.md)）。

| 段階 | やりたいこと | Skill |
|---|---|---|
| 0. 準備 | 関係者と役割、AIに読ませてよい範囲、様式を決める | `/banto:setup` |
| 1. 様式 | 顧客・会社の専用様式を取り込む（配置の認識合わせ → 対応づけ） | `/banto:format-intake` |
| 2. 取り込み | 既存プロジェクトの情報源を突き合わせる | `/banto:import` |
| 3. 網羅 | 設計書を作る情報が揃っているか、何が足りず何が不要か | `/banto:coverage` |
| 4. 判断と補完 | 判断票を見て判断し、記録して実物を直す | `/banto:decision-sheet` `/banto:apply-decision` |
| 5. 清書とレビュー | 様式どおりのExcelとレビュー表を出し、指摘を取り込む | `/banto:export-excel` `/banto:import-review` |
| 6. 提出 | 版を提出版として確定する（承認者） | `/banto:release` |
| 7. 変更 | 変更のあと、ずれを確かめる | `/banto:check-drift` |

役割を分けたエージェント（`extractor` 抽出係、`matcher` 照合係、`applier` 反映係、`auditor` 監査係）が、Skillの中で使われます。どの係も「どれが正か」は決めません。

### コマンドだけで使う

```
python3 scripts/banto.py --project <対象> init --system 名前 --judge 名前 --approver 名前
python3 scripts/banto.py --project <対象> sync
python3 scripts/banto.py --project <対象> coverage
python3 scripts/banto.py --project <対象> decide DRF-0017 --set 10 --by 名前 --reason "10桁に統一"
python3 scripts/banto.py --project <対象> decide --item BD-07 --exclude --by 名前 --reason "帳票の要件なし"
python3 scripts/banto.py --project <対象> export
python3 scripts/banto.py --project <対象> release TD --by 承認者 --reason "初回提出"
python3 scripts/banto.py --project <対象> format read 顧客様式.xlsx --name 顧客A
python3 scripts/banto.py --project <対象> import-review review-RV001.xlsx
python3 scripts/banto.py --project <対象> check --strict
```

情報源の一覧（`banto/sources.json`）・案件の設定（`banto/project.json`）・台帳・判断票・様式の形式は [docs/spec.md](docs/spec.md)。
専用様式を試すための架空の様式は `python3 examples/make_customer_template.py` で作れます。

## 文書

- [docs/concept.md](docs/concept.md) — 構想（なぜ、何を、どう分担するか）
- [docs/spec.md](docs/spec.md) — 規約（ファイルの形、IDの体系、値の書き方）
- [tools/README.md](tools/README.md) — スクリプトの構成と開発

## 状態

v0.2。案件の流れの全段階（準備・様式・取り込み・網羅・判断・清書とレビュー・提出・変更）を実装。
情報源はテーブル定義（MD・Excel設計書、DDL〔H2・MySQL・PostgreSQL〕、JPA）とテスト（MDの仕様書・報告書、JUnit 5、surefire）。

テスト：`python3 -m unittest discover -s tests`
