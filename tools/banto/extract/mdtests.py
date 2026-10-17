"""MDのテスト仕様書・テスト報告書から、テストクラスごとのテストメソッド表を取り出す。

想定する形:
  ## 1. Unit Test — `OwnerTests.java`      ← 見出しに `クラス名.java`（または `クラス名`）
  | テストメソッド | 種別 | 検証内容 |        ← 先頭列がテストメソッド
  | `Inner#method()` | 正常系 | ... |
列の対応（見出し名 → 属性）は sources.json の "columns" で指定する。
"""
import re

HEADING = re.compile(r"^#{1,6}\s")
HEAD = re.compile(r"^#{1,6}\s+.*?`([A-Z]\w*)(?:\.java)?`")
METHOD_HEADERS = ("テストメソッド", "メソッド", "テスト")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def method_key(text):
    t = text.strip().strip("`").strip()
    t = re.sub(r"\(.*?\)$", "", t)
    return t.replace("$", "#")


def result_value(text):
    u = text.upper()
    for k, v in (("FAIL", "fail"), ("ERROR", "error"), ("SKIP", "skipped"), ("PASS", "pass")):
        if k in u:
            return v
    if "✅" in text:
        return "pass"
    if "❌" in text:
        return "fail"
    return None


def extract(src, text, columns, sections=None):
    lines = text.splitlines()
    current, i = None, 0
    while i < len(lines):
        if HEADING.match(lines[i]):
            level = len(lines[i]) - len(lines[i].lstrip("#"))
            m = HEAD.match(lines[i])
            if m:
                current = (m.group(1), i + 1, level)
            elif current and level <= current[2]:
                current = None   # 同じか上の階層の見出しで、クラスの節が終わる
            elif current and sections:
                # クラスの節の中の小見出し（例:「### 目的」）の本文を、コンテナの属性として取り出す
                title = lines[i].lstrip("#").strip()
                if title in sections:
                    body, j = [], i + 1
                    while j < len(lines) and not HEADING.match(lines[j]) and not lines[j].lstrip().startswith("|"):
                        if lines[j].strip() and lines[j].strip() != "---":
                            body.append(lines[j].strip())
                        j += 1
                    if body:
                        cont = src.container(current[0], f"{src.path}:{current[1]}")
                        cont.set(sections[title], " ".join(body), " ".join(body), f"{src.path}:{i + 1}")
        elif lines[i].lstrip().startswith("|") and current and cells(lines[i])[0] in METHOD_HEADERS:
            header = cells(lines[i])
            cont = src.container(current[0], f"{src.path}:{current[1]}")
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                row = cells(lines[j])
                key = method_key(row[0])
                if key:
                    it = cont.item(key, f"{src.path}:{j + 1}")
                    for h, attr in columns.items():
                        if h in header and header.index(h) < len(row):
                            raw = row[header.index(h)]
                            if attr == "result":
                                v = result_value(raw)
                                if v:
                                    it.set("result", v, f"{raw}（列「{h}」）")
                            elif raw:
                                it.set(attr, raw, raw)
                j += 1
            i = j
            continue
        i += 1
