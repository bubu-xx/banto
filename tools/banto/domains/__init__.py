from . import tables, tests

DOMAINS = {"tables": tables, "tests": tests}


def get(name):
    return DOMAINS[name].DOMAIN


def all_domains():
    return [m.DOMAIN for m in DOMAINS.values()]
