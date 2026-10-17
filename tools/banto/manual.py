"""人が書く節と表（banto/manual/<項目ID>.md）。

様式の項目のうち、実物から取り出せない情報（システム概要、画面一覧など）を、人が書く場所。
網羅の確認で、該当する項目のひな形が作られる。ひな形のままなら「情報不足」として扱う。
"""
import os
import re
from . import fio, frontmatter

TABLE = "<!-- banto:table -->"
HINT = re.compile(r"<!--.*?-->", re.S)


def path(base, item_id):
    return os.path.join(base, "manual", f"{item_id}.md")


def skeleton(doc, item):
    meta = {"id": item["id"], "title": item["title"], "document": doc["title"], "status": "draft"}
    L = [frontmatter.dump(meta), f"# {item['id']} {item['title']}", "",
         f"<!-- 書くこと：{item.get('hint', '')}。書き終えたら status を confirmed にする -->", ""]
    if item["kind"] == "manual-table":
        cols = item["columns"]
        L += [TABLE, "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols), ""]
    return "\n".join(L)


def load(base, item_id):
    p = path(base, item_id)
    if not os.path.exists(p):
        return None
    meta, body = frontmatter.load(fio.read(p))
    out = {"path": p, "meta": meta, "body": body, "rows": [], "header": []}
    if TABLE in body:
        lines = body.split(TABLE, 1)[1].splitlines()
        i = 0
        while i < len(lines) and not lines[i].lstrip().startswith("|"):
            i += 1
        if i < len(lines):
            out["header"] = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if any(cells):
                    out["rows"].append(dict(zip(out["header"], cells)))
                j += 1
    return out


def prose(body):
    """見出し・コメント・表を除いた本文（充足の判定と、Excelへの出力に使う）。"""
    text = HINT.sub("", body.split(TABLE, 1)[0])
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()
