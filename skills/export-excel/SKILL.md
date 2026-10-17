---
name: export-excel
description: bantoの台帳から、提出用のExcel（テーブル定義書・テスト仕様書）と空のレビュー表を清書する。Use when the user wants Excel documents for submission or review, says "Excelで出して", "設計書を清書して", "レビュー用に出力", or runs /banto:export-excel.
---

# Excel清書

台帳MDが原本で、Excelは提出用の写し。Excelを直接直すと原本とずれるので、本体のシートは保護してある。

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> export
```

Windows では `python3` を `python` に置き換える。出力先を変えるときは `--out <フォルダ>` を `export` の後ろに付ける。

## 手順

1. 先に同期され、出力の直前に未判断・直し待ちの件数が確定する。未判断が残っていると、その値はExcelで「未定（DRF-xxxx）」になる。残っていればユーザーに伝え、このまま出すか確かめる。
2. 出力されたファイルを伝える（既定は `banto/export/`）：
   - `tables.xlsx` / `tests.xlsx`：表紙・改訂履歴・一覧・本体・許容された差・未判断／直し待ち
   - `review-RVxxx.xlsx`：空のレビュー表（入力規則つき）、ID一覧、これまでの指摘と対応
3. 版は台帳の中身が前回の出力から変わったときだけ上がり、改訂履歴に反映した判断が残る。

## 伝えること

- 指摘はExcelの本体ではなくレビュー表に、**各行のID（TBL- / COL- / TSU- / TC-）** を添えて書いてもらう
- 記入済みのレビュー表は `/banto:import-review` で取り込む

## 防ぐ失敗

Excelに直接赤入れされ、その修正がMDに戻らず、原本と提出物が二重管理になる。
