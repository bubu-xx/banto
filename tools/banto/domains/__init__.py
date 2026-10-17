from . import tables, tests

DOMAINS = {"tables": tables, "tests": tests}


def get(name):
    return DOMAINS[name].DOMAIN


def all_domains():
    return [m.DOMAIN for m in DOMAINS.values()]


def configure(project_cfg):
    """案件の設定に合わせて、各領域の「人が書く列」を整える（同期のたびに呼ぶ）。"""
    extra = (project_cfg or {}).get("extra_columns", {}) or {}
    for name, mod in DOMAINS.items():
        mod.DOMAIN.configure(extra.get(name, ()))
