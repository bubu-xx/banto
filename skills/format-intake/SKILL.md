---
name: format-intake
description: 顧客や会社の専用様式（Excelのテンプレート）を受け取り、どこに何があるかの認識を人と合わせてから、bantoの情報に対応づけて、その様式で出力できるようにする。Use when the user provides a template, says "この様式で出して", "顧客のテンプレート", "フォーマットを渡す", or runs /banto:format-intake.
---

# 専用様式の取り込み（段階1）

**配置（どこに何があるか）を合わせてから、対応づけ（そこに何を入れるか）に進む。** 順番を飛ばさない。

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> format <read|trial|confirm|map> ...
```

Windows では `python3` を `python` に置き換える。以下 `banto <コマンド>` と書く。

## 手順

### 1. 配置の認識を合わせる

1. `banto format read <様式.xlsx> --name <様式名>` で構造を読む。`banto/format/<様式名>/` に STRUCTURE.md（読み取り結果）と layout.json（配置の下書き）ができる
2. 下書きを確かめ、直す。layout.json の各シートについて：
   - `role`：`cover`（表紙）／`history`（改訂履歴）／`per-container`（テーブルごとに1枚）／`list`（一覧）／`other`
   - `fields`：見出し（label）と、値を入れるセル（cell）。結合セルは左上のセル
   - `tables`：見出しの行、明細の最初と最後の行、各列の見出し
   - 見落とし（例：見出しが縦に並ぶ欄、2段の見出し）がないか、STRUCTURE.md の「確認したいこと」を含めてユーザーに聞く
3. `banto format trial --name <様式名>` で試し刷り（各欄に「［見出し］」が入ったExcel）を作る。LibreOffice があれば画像にして見せる（`soffice --headless --convert-to pdf`）。無ければファイルを開いてもらう
4. ユーザーが「合っている」と言ったら `banto format confirm --name <様式名> --step layout --by <名前>`

### 2. 対応づける

1. `banto format map --name <様式名> --doc-id <文書ID> --doc-title <文書名>` で対応づけの下書き（mapping.json）を作る
2. 「要確認」に出た欄を、ユーザーと決める。使える値：
   - 表紙など：`project.system` `project.project` `project.customer` `doc.title` `doc.version` `doc.date` `doc.author` `doc.approver`
   - テーブルごとの欄：`container.name` `container.title`（論理名）`container.summary`（説明）`container.id`
   - 明細の列：`item.no` `item.name` `item.logical_name` `item.base_type` `item.length` `item.scale` `item.nullable` `item.pk` `item.fk` `item.default` `item.indexed` `item.description`
   - bantoに無い列：`item.free:<見出し>`（人が書く列として台帳に足す）。入れない欄は `none`
   - 改訂履歴の列：`history.version` `history.date` `history.note` `history.by`
3. `banto format trial --name <様式名> --data` で、実際の値が入った試し刷りを作って確かめる
4. `banto format confirm --name <様式名> --step mapping --by <名前>`。人が書く列が project.json の `extra_columns` に足される
5. project.json の `format` を `"custom:<様式名>"` にする。以後、網羅表はこの様式を基準に、`banto export` はこの様式で出力する

## ルール

- 推定した配置・対応を、確かめずに確定しない
- 様式の画像（ロゴなど）は、出力で失われることがある。気づいたら伝える

## 防ぐ失敗

様式の読み違い（2段の見出し、別シートの欄）に気づかないまま値を流し込み、提出の直前に崩れた設計書が出る。
