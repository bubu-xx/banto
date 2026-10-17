---
name: release
description: 設計書の版を提出版として確定する（承認）。残っている未判断・情報不足の扱いと、前回提出版からの変更を記録する。Use when the user wants to submit or approve a document version, says "提出する", "この版で確定", "承認", or runs /banto:release.
---

# 承認・提出（段階6）

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> release <文書ID> --by <承認者> --reason "<承認の理由・条件>"
```

Windows では `python3` を `python` に置き換える。文書IDは様式の文書（標準様式なら BD・DD・TD・TS）。

## 手順

1. 提出前の状態を確かめる：`banto status` と網羅表で、その文書の未判断・直し待ち・情報不足・要不要が未判断の項目を見る
2. 残っているものがあれば、承認者に一覧を見せて判断してもらう
   - 解消してから提出する（推奨）
   - 了承して提出する：`--allow-open` を付け、`--reason` に了承の条件（例：「次版で解消する」）を書く。提出記録に残課題として残る
3. 提出する。承認者として登録された人でなければ実行できない（`project.json` の people）
4. 出たものを伝える：`banto/releases/<文書ID>-v<版>/`（提出したExcel、RELEASE.md、中身の写し）。2回目以降は RELEASE.md に「前回提出版からの変更」が出る

## ルール

- 承認するのは承認者。代わりに `--allow-open` を付けない
- 同じ版は二度提出できない。直したら出し直すと次の版になる

## 防ぐ失敗

どの版をいつ誰が承認し、何を未解決のまま出したかが残らず、検収や障害の後で説明できない。
