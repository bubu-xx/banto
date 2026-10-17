---
name: import-review
description: 記入済みのbantoレビュー表（review-RVxxx.xlsx）を取り込み、指摘を判断票にして対応を進める。Use when the user brings back a filled review sheet, says "レビュー表を取り込んで", "指摘が返ってきた", or runs /banto:import-review.
---

# レビュー表の取り込み

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> import-review <記入済みのレビュー表.xlsx>
```

Windows では `python3` を `python` に置き換える。

## 手順

1. 取り込む。同じレビュー表を取り込み直すと、前回の取り込みを置き換える（指摘が増減しても重複しない）。
2. 注意（箇所のIDが台帳にない、IDが空）が出たら、指摘者に箇所を確かめる必要があることをユーザーに伝える。
3. 指摘ごとに判断票ができる（`banto/drifts/` の、領域が review のもの）。判断票には指摘の内容と、指摘箇所の台帳の値が並ぶ。
4. 対応はユーザーが決め、`/banto:apply-decision` で記録する：
   - 受け入れて台帳を直す：`--accept --target <ID> --attr <属性名> --set <値>`（実物の直し待ちが自動で出る）
   - 受け入れる（台帳の値は変えない）：`--accept`
   - 受け入れない：`--reject`
   - 質問に回答：`--answer`
5. 次に `/banto:export-excel` で出すと、レビュー表の「これまでの指摘と対応」に、対応方針と内容が載る。

## 防ぐ失敗

指摘への対応が、誰がどう決めたか残らず、「直したはず」の箇所が次の版で元に戻る。
