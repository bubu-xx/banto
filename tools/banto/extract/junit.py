"""JUnit 5 のテストコードから、テストクラスとテストメソッドを取り出す。

@Nested の内側のメソッドは「内側クラス名#メソッド名」で表す（surefire や仕様書の書き方に合わせる）。
"""
import os
import re
from .. import fio

TEST_ANN = re.compile(r"^\s*@(Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b")
CLASS = re.compile(r"\bclass\s+(\w+)")


def _strip(line):
    line = re.sub(r"\"(?:\\.|[^\"\\])*\"", "\"\"", line)
    return re.sub(r"//.*$", "", line)


def parse_file(path):
    """戻り値: (トップクラス名, [(キー, 行番号)])"""
    lines = fio.read(path, errors="ignore").splitlines()
    stack, depth, pending_class, pending_test, top, tests = [], 0, None, False, None, []
    in_block = False
    for n, raw in enumerate(lines, 1):
        line = raw
        if in_block:
            if "*/" in line:
                line, in_block = line.split("*/", 1)[1], False
            else:
                continue
        if "/*" in line and "*/" not in line.split("/*", 1)[1]:
            line, in_block = line.split("/*", 1)[0], True
        line = _strip(line)
        if TEST_ANN.match(line):
            pending_test = True
        m = CLASS.search(line)
        if m and not line.strip().startswith(("@", "*")):
            pending_class = m.group(1)
            top = top or pending_class
        elif pending_test:
            mm = re.search(r"\b(\w+)\s*\(", line)
            if mm and not line.strip().startswith("@") and mm.group(1) not in ("if", "for", "while"):
                inner = stack[-1][0] if len(stack) > 1 else None
                tests.append((f"{inner}#{mm.group(1)}" if inner else mm.group(1), n))
                pending_test = False
        for ch in line:
            if ch == "{":
                depth += 1
                if pending_class:
                    stack.append((pending_class, depth))
                    pending_class = None
            elif ch == "}":
                if stack and stack[-1][1] == depth:
                    stack.pop()
                depth -= 1
    return top, tests


def extract(src, root, base_dir):
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.endswith(".java"):
                continue
            p = os.path.join(dp, f)
            top, tests = parse_file(p)
            if not top or not tests:
                continue
            rel = os.path.relpath(p, base_dir).replace(os.sep, "/")
            c = src.container(top, f"{rel}:1")
            for key, n in tests:
                c.item(key, f"{rel}:{n}")
