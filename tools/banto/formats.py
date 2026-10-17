"""様式（設計書の章立てと項目の定義）の読み込みと、該当判定の手がかりの照合。

標準様式は banto リポジトリの formats/standard/format.json。
専用様式は対象プロジェクトの banto/format/<名前>/format.json（専用様式の取り込みで作られる）。
"""
import json
import os
import re
from . import fio

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "formats"))
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "banto", ".venv", "venv", "__pycache__", ".idea", ".gradle"}


def load(base, name):
    """name: "standard" または "custom:<名前>"。"""
    if name.startswith("custom:"):
        p = os.path.join(base, "format", name.split(":", 1)[1], "format.json")
    else:
        p = os.path.join(ROOT, name, "format.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"様式が見つからない: {p}")
    fmt = json.loads(fio.read(p))
    fmt["_path"] = p
    return fmt


def items(fmt):
    for doc in fmt["documents"]:
        for it in doc["items"]:
            yield doc, it


def item_ids(fmt):
    return {it["id"]: (doc, it) for doc, it in items(fmt)}


# ---------------------------------------------------------------- 手がかりの照合

def _braces(p):
    m = re.search(r"\{([^{}]*)\}", p)
    if not m:
        return [p]
    return [x for alt in m.group(1).split(",") for x in _braces(p[:m.start()] + alt + p[m.end():])]


def _glob_re(pattern):
    out = []
    for p in _braces(pattern):
        r, i = "", 0
        while i < len(p):
            if p.startswith("**/", i):
                r += "(?:.*/)?"
                i += 3
            elif p.startswith("**", i):
                r += ".*"
                i += 2
            elif p[i] == "*":
                r += "[^/]*"
                i += 1
            elif p[i] == "?":
                r += "[^/]"
                i += 1
            else:
                r += re.escape(p[i])
                i += 1
        out.append(re.compile("^" + r + "$"))
    return out


class Scanner:
    """対象プロジェクトのファイルを一度だけ列挙し、手がかり（glob / grep）を照合する。"""

    def __init__(self, project):
        self.project = project
        self.files = []
        for dp, dns, fns in os.walk(project):
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and not d.startswith("."))
            for f in sorted(fns):
                self.files.append(os.path.relpath(os.path.join(dp, f), project).replace(os.sep, "/"))
        self._text = {}

    def _read(self, rel):
        if rel not in self._text:
            p = os.path.join(self.project, rel)
            try:
                self._text[rel] = fio.read(p, errors="ignore") if os.path.getsize(p) < 1_000_000 else ""
            except OSError:
                self._text[rel] = ""
        return self._text[rel]

    def match(self, signal):
        """一致した根拠（"ファイル" か "ファイル:行"）を返す。なければ None。"""
        if "glob" in signal and "grep" not in signal:
            pats = _glob_re(signal["glob"])
            for f in self.files:
                if any(p.match(f) for p in pats):
                    return f
            return None
        pats = _glob_re(signal.get("files", "**/*"))
        rx = re.compile(signal["grep"])
        for f in self.files:
            if any(p.match(f) for p in pats):
                for n, ln in enumerate(self._read(f).splitlines(), 1):
                    if rx.search(ln):
                        return f"{f}:{n}"
        return None

    def describe(self, signal):
        if signal.get("label"):
            return signal["label"]
        if "grep" in signal:
            return f"`{signal['grep']}` を含む {signal.get('files', 'ファイル')}"
        return f"`{signal['glob']}` に当たるファイル"
