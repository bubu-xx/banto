"""Maven surefire / Gradle の JUnit XML（TEST-*.xml）から、テストごとの実行結果を取り出す。

実行結果は「実行されたテスト」しか分からないため、有無の比較には参加しない（結果だけを提供する）。
"""
import os
import re
import xml.etree.ElementTree as ET

RANK = {"pass": 0, "skipped": 1, "fail": 2, "error": 3}


def extract(src, root, base_dir):
    if not os.path.isdir(root):
        return
    for f in sorted(os.listdir(root)):
        if not (f.startswith("TEST-") and f.endswith(".xml")):
            continue
        p = os.path.join(root, f)
        rel = os.path.relpath(p, base_dir).replace(os.sep, "/")
        try:
            tree = ET.parse(p)
        except ET.ParseError:
            continue
        for tc in tree.iter("testcase"):
            cls = tc.get("classname", "")
            name = re.sub(r"\[.*?\]$", "", re.sub(r"\(.*?\)", "", tc.get("name", ""))).strip()
            parts = cls.split(".")[-1].split("$")
            top, inner = parts[0], (parts[-1] if len(parts) > 1 else None)
            key = f"{inner}#{name}" if inner else name
            if tc.find("error") is not None:
                v = "error"
            elif tc.find("failure") is not None:
                v = "fail"
            elif tc.find("skipped") is not None:
                v = "skipped"
            else:
                v = "pass"
            c = src.container(top, rel)
            it = c.item(key, rel)
            prev = it.attrs.get("result")
            if prev is None or RANK[v] > RANK[prev.value]:
                msg = ""
                el = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
                if el is not None:
                    detail = re.sub(r"\s+", " ", el.get("message") or "")[:90]
                    msg = (el.get("type") or "").split(".")[-1] + (f": {detail}" if detail else "")
                it.set("result", v, f"{v}{'（' + msg + '）' if msg else ''}（{tc.get('time', '?')}s）", rel)
