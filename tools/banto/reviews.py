"""レビュー指摘の取り込み結果（banto/reviews/*.json）の読み込み。取り込み自体は review_io.py。"""
import json
import os
from . import fio


def load(base):
    d = os.path.join(base, "reviews")
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            out += json.loads(fio.read(os.path.join(d, f)))
    return out
