"""banto/state/ に置く、機械用の状態（IDの採番表、ずれの登録簿、適用済みの判断）。

どれも人が読む必要はないが、Gitで差分が読めるよう、キーを並べ替えて決まった形で書き出す。
"""
import json
import os
from . import fio


def key(domain, container, item=None, attr="exists"):
    return f"{domain}|{container}|{item or ''}|{attr}"


def split(k):
    d, c, i, a = k.split("|", 3)
    return d, c, (i or None), a


class State:
    def __init__(self, base):
        self.dir = os.path.join(base, "state")
        self.ids = self._load("ids.json", {"containers": {}, "items": {}, "counters": {}})
        self.drifts = self._load("drifts.json", {})        # key -> {id, status, decision?, value?}
        self.applied = self._load("applied.json", [])      # 台帳に適用済みの DEC-ID
        self.coverage = self._load("coverage.json", {})    # 様式の項目ID -> {decision, applicable}

    def _load(self, name, default):
        p = os.path.join(self.dir, name)
        if os.path.exists(p):
            return json.loads(fio.read(p))
        return default

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        for name, obj in (("ids.json", self.ids), ("drifts.json", self.drifts), ("applied.json", sorted(self.applied)),
                          ("coverage.json", self.coverage)):
            text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
            p = os.path.join(self.dir, name)
            if not os.path.exists(p) or fio.read(p) != text:
                fio.write(p, text)

    def _next(self, prefix, width):
        n = self.ids["counters"].get(prefix, 0) + 1
        self.ids["counters"][prefix] = n
        return f"{prefix}-{n:0{width}d}"

    def container_id(self, domain, prefix, container):
        k = f"{domain}|{container}"
        if k not in self.ids["containers"]:
            self.ids["containers"][k] = self._next(prefix, 3)
        return self.ids["containers"][k]

    def item_id(self, domain, prefix, container, item):
        k = f"{domain}|{container}|{item}"
        if k not in self.ids["items"]:
            self.ids["items"][k] = self._next(prefix, 3)
        return self.ids["items"][k]

    def drift_id(self):
        return self._next("DRF", 4)

    def dec_id(self, existing):
        n = max([int(x.split("-")[1]) for x in existing] + [0]) + 1
        return f"DEC-{n:04d}"

    def by_drift_id(self):
        return {v["id"]: k for k, v in self.drifts.items()}

    def by_target_id(self):
        out = {}
        for k, v in self.ids["containers"].items():
            d, c = k.split("|", 1)
            out[v] = (d, c, None)
        for k, v in self.ids["items"].items():
            d, c, i = k.split("|", 2)
            out[v] = (d, c, i)
        return out
