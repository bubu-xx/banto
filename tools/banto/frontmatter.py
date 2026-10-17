"""MDの先頭の frontmatter（--- で囲んだ key: value）を読み書きする。YAMLの小さな部分集合だけを扱う。"""
import re


def _quote(v):
    s = str(v)
    if s == "" or re.search(r"[:#\[\],\"']|^\s|\s$", s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def dump(meta):
    out = ["---"]
    for k, v in meta.items():
        if isinstance(v, (list, tuple)):
            out.append(f"{k}: [{', '.join(_quote(x) for x in v)}]")
        else:
            out.append(f"{k}: {_quote(v)}")
    out.append("---")
    return "\n".join(out) + "\n"


def _split_list(s):
    items, cur, q = [], "", False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == "," and not q:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur)
    return [_unquote(x) for x in items]


def load(text):
    """戻り値: (meta, 本文)"""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        meta[k.strip()] = _split_list(v[1:-1]) if v.startswith("[") and v.endswith("]") else _unquote(v)
    return meta, text[m.end():]
