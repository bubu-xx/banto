---
name: setup
description: bantoを案件で使い始める準備をする。関係者と役割（判断者・承認者・作成者）、AIに読ませてよい範囲、提出する様式を決めて banto/project.json に書く。Use when starting banto on a project, says "bantoを始めたい", "案件の準備", "判断者を登録して", or runs /banto:setup.
---

# 準備（段階0）

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> <コマンド>
```

Windows では `python3` を `python` に置き換える。以下 `banto <コマンド>` と書く。

## 手順

1. ユーザーに次を確かめる（分からないものは空欄でよいが、空欄にしたことを伝える）
   - システム名・案件名・顧客名（表紙に出る）
   - 判断者（ずれや要不要を決める人）、承認者（提出版を確定する人）、作成者（人が書く情報を書く人）
   - **AIにコードや文書を読ませてよいか**（契約・情報管理の規程で確認済みか）
   - 提出する様式：顧客や会社の専用様式があるか（あれば `/banto:format-intake`）。なければ標準様式
2. `banto init --system <システム名> --name <案件名> --customer <顧客> --judge <名前> --approver <名前>` を実行する（既存のファイルは上書きしない）
3. `banto/project.json` を開き、`people`（作成者は roles に `author`）、`ai_policy`（`code_access` に確認結果、`note` に根拠）を書き足す
4. 次は `/banto:import`（情報源の取り込み）か、専用様式があれば `/banto:format-intake`

## ルール

- AIに読ませてよいかが未確認なら、取り込みに進まない。ユーザーに確認を促す
- 役割を登録すると、`decide` は判断者、`release` は承認者でなければ実行できなくなることを伝える

## 防ぐ失敗

誰の判断が有効か決まらないまま進み、提出の直前に「その判断は誰が承認したのか」と問われる。
