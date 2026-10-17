---
name: apply-decision
description: 人が下した判断をbantoの判断の記録（DEC）として残し、台帳に反映して、実物（DDL・コード・文書）の直し作業まで進める。Use when the user states a decision about a drift ("これは方言差として許容", "10桁に統一する", "仕様書から削除"), answers a review comment, or runs /banto:apply-decision.
---

# 判断の反映

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> <コマンド>
```

Windows では `python3` を `python` に置き換える。以下 `banto <コマンド>` と書く。

## 手順

1. **判断の中身を確定させる**：対象（`DRF-xxxx` か グループ）、選んだ選択肢、判断した人、理由。どれかが曖昧なら聞き返す。**理由は必須**（次の判断の材料になる）。
2. **記録する**（ユーザーの言葉どおりに。言い換えて別の判断にしない）：
   - 値を正とする：`banto decide DRF-0017 --set 10 --by <名前> --reason "<理由>"`
   - 意図した違いとして許容：`banto decide DRF-0030 --allow --by <名前> --reason "<理由>"`（台帳の値が未定なら `--value <代表の値>`）
   - グループをまとめて：`banto decide --group "<グループ>" --allow --value × --by <名前> --reason "<理由>"`
   - 有無：`--set あり` / `--set なし` / `--allow --value あり`（範囲外として許容）
   - レビュー指摘：`--accept`（台帳を直すなら `--target <ID> --attr <属性名> --set <値>`）/ `--reject` / `--answer`
3. **結果を伝える**：コマンドが各ずれの状態を表示する。`decided`（直し待ち）なら `banto/drifts/APPLY.md` に作業が出る。
4. **実物を直す**：APPLY.md の作業を `applier` エージェントに渡す（コードやDDLを変えるので、着手前にユーザーの了承を取る）。直したら `banto sync`。
5. **確認する**：`auditor` エージェントに、判断どおりに直ったか、新しいずれが出ていないかを確認させる。

属性名（`--attr`）：テーブルは `base_type` `length` `nullable` `pk` `fk` `indexed` `identity` `case_insensitive` `unsigned` `unique`、テストは `category` `purpose` `result`。

## ルール

- 判断はユーザーのもの。記録する前に、対象と選択肢を1行で復唱して確認する
- 一括判断は、グループの全件に同じ規則が当てはまるかをユーザーに確かめてから
- 判断に疑問が出たら、直さずにユーザーへ戻す（判断の中身を勝手に変えない）

## 防ぐ失敗

口頭やチャットで決めたことが記録されず、半年後に同じ議論を繰り返す。実物の直しが漏れ、決めたことと実物がずれたままになる。

例：「telephoneは10桁に統一」と決めたが、PostgreSQLのDDLだけ直し忘れる。判断は DEC に残り、直し待ちのリストに PostgreSQL が残り続けるので、漏れが見える。
