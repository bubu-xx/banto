"""ファイルの読み書き。文字コードは UTF-8、改行は OS に関係なく LF に揃える（Windowsでも差分が出ないように）。"""
import os


def read(path, errors="strict"):
    with open(path, encoding="utf-8", errors=errors, newline=None) as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
