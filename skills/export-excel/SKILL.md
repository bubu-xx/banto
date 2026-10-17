---
name: export-excel
description: bantoの台帳と人が書いた節から、様式どおりのExcel（基本設計書・詳細設計書・テーブル定義書・テスト仕様書、または専用様式）と空のレビュー表を清書する。Use when the user wants Excel documents for submission or review, says "Excelで出して", "設計書を清書して", "レビュー用に出力", or runs /banto:export-excel.
---

# Excel清書（段階5）

台帳MDと `banto/manual/` が原本で、Excelは提出用の写し。Excelを直接直すと原本とずれるので、本体のシートは保護してある。

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> export [--doc TD] [--out <フォルダ>]
```

Windows では `python3` を `python` に置き換える。`--doc` を省くとすべての文書を出す。

## 手順

1. 出力の前に同期され、未判断・情報不足の件数が確定する。残っていれば、その箇所はExcelで「未定（DRF-xxxx）」「情報不足」「未記入」と明示される。ユーザーに件数を伝え、このまま出すか確かめる
2. 出力されたファイルを伝える（既定は `banto/export/`）
   - 標準様式：`BD_基本設計書.xlsx` `DD_詳細設計書.xlsx` `TD_テーブル定義書.xlsx` `TS_テスト仕様書.xlsx`。各冊に表紙・改訂履歴・目次・本体・未判断と情報不足。不要と判断した項目は目次に「対象外（理由）」として載る
   - 専用様式（project.json の format が `custom:<名前>`）：`<文書ID>_<名前>.xlsx`。様式に値を入れたもの
   - `review-RVxxx.xlsx`：空のレビュー表（入力規則つき）、ID一覧（項目ID・テーブル・列・テスト）、これまでの指摘と対応
3. 版は文書の中身が前回の出力から変わったときだけ上がり、改訂履歴に「何が変わったか」と判断した人が残る

## 伝えること

- 指摘はExcelの本体ではなくレビュー表に、**ID**（項目ID BD-01、テーブル TBL-、列 COL-、テスト TC- など）を添えて書いてもらう
- 記入済みのレビュー表は `/banto:import-review` で取り込む
- 提出版として確定するのは `/banto:release`（承認者）

## 防ぐ失敗

Excelに直接赤入れされ、その修正がMDに戻らず、原本と提出物が二重管理になる。
