---
name: check-drift
description: 変更のあとに、bantoの台帳と実物（設計書・DDL・コード・テスト結果）を照らし合わせ、新しく生じたずれと解決したずれを報告する。Use after code, DDL or document changes, before a commit or pull request, when the user says "ずれを確認して", "台帳と合ってる？", "banto sync", or runs /banto:check-drift.
---

# ずれの確認（運用中）

## 実行のしかた

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banto.py" --project <対象プロジェクト> <コマンド>
```

Windows では `python3` を `python` に置き換える。以下 `banto <コマンド>` と書く。

## 手順

1. `banto sync` を実行する。台帳・判断票・一覧（`banto/drifts/README.md`）・直し待ちリスト（`banto/drifts/APPLY.md`）・網羅表（`banto/coverage/README.md`）が更新される。
2. `banto check` で記録の整合を確かめる（IDの鎖が切れていないか、判断の記録に誤りがないか）。CIでは `banto check --strict` を使う（未判断・直し待ちが残っていれば失敗）。
3. 前回からの変化を報告する：
   - 新しく **未判断** になったもの（台帳と実物が食い違った）
   - **解決済み** になったもの（直し待ちの実物が直った）
   - 解決済みから **未判断に戻った** もの（判断票の「以前の判断」に経緯が出る）
4. 新しいずれがあれば `/banto:decision-sheet` へつなぐ。

## 台帳を直接書き換えた場合

台帳MDは原本なので、人が値を書き換えてよい（設計変更）。次の同期で、実物との差が「台帳と異なる」ずれとして出る。
そのずれを判断して（多くは「台帳の値を正とする」）、実物を直す流れになる。

## 防ぐ失敗

コードやDDLだけ直して設計書が置き去りになり、半年後に誰も正しい仕様を言えなくなる。

例：PostgreSQLのマイグレーションで列長を変えた。同期で「長さ：DDL（PostgreSQL） が台帳と異なる」が出て、設計書を直すか、変更を戻すかの判断を求められる。
