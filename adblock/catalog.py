"""Filter-list catalog and storage layout (no networking here; Qt glue downloads).

Lists are downloaded at runtime into HOME/.luna_adblock/lists/<id>.txt (+ <id>__<include>.txt) and are
never committed (licences: GPL-3, CC BY-SA 3.0, CC BY-NC-SA 4.0, MPL-2.0).
"""
import json
import os
import time

_UBO = "https://ublockorigin.github.io/uAssetsCDN/filters/%s.min.txt"
_UBO_FB = "https://ublockorigin.pages.dev/filters/%s.min.txt"
_UBO_HOME = "https://github.com/uBlockOrigin/uAssets"


def _ubo(id_, name, title, desc, expires_h=120):
    return dict(id=id_, title=title, desc=desc, url=_UBO % name, fallback=_UBO_FB % name, homepage=_UBO_HOME,
                license="GPL-3.0", expires_h=expires_h, trusted=True, default_on=True, includes=[], kind="filters")


LISTS = [
    _ubo("ubo-filters", "filters", "uBlock filters – Reklamy", "Główna lista uBlock Origin: reklamy, anty-adblock."),
    _ubo("ubo-badware", "badware", "uBlock filters – Zagrożenia", "Strony ze złośliwym oprogramowaniem i oszustwa."),
    _ubo("ubo-privacy", "privacy", "uBlock filters – Prywatność", "Śledzenie i nadużycia zasobów."),
    _ubo("ubo-quick-fixes", "quick-fixes", "uBlock filters – Szybkie poprawki",
         "Pilne poprawki dla popularnych stron.", expires_h=12),
    _ubo("ubo-unbreak", "unbreak", "uBlock filters – Naprawy", "Wyjątki naprawiające zepsute strony."),
    dict(id="easylist", title="EasyList", desc="Podstawowa międzynarodowa lista reklam.",
         url="https://ublockorigin.github.io/uAssetsCDN/thirdparties/easylist.txt",
         fallback="https://ublockorigin.pages.dev/thirdparties/easylist.txt",
         homepage="https://easylist.to/", license="GPL-3.0 / CC BY-SA 3.0", expires_h=120,
         trusted=False, default_on=True, includes=[], kind="filters"),
    dict(id="easyprivacy", title="EasyPrivacy", desc="Blokowanie skryptów śledzących i analityki.",
         url="https://ublockorigin.github.io/uAssetsCDN/thirdparties/easyprivacy.txt",
         fallback="https://ublockorigin.pages.dev/thirdparties/easyprivacy.txt",
         homepage="https://easylist.to/", license="GPL-3.0 / CC BY-SA 3.0", expires_h=120,
         trusted=False, default_on=True, includes=[], kind="filters"),
    dict(id="pgl", title="Peter Lowe – serwery reklam", desc="Lista domen reklamowych i śledzących (format hosts).",
         url="https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext",
         fallback=None, homepage="https://pgl.yoyo.org/adservers/", license="© Peter Lowe (darmowa do użytku)",
         expires_h=168, trusted=False, default_on=True, includes=[], kind="filters"),
    dict(id="pol0", title="Oficjalne Polskie Filtry (POL-0)", desc="Polskie reklamy i anty-adblock (MajkiIT).",
         url="https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock.txt",
         fallback=None, homepage="https://github.com/MajkiIT/polish-ads-filter", license="CC BY-NC-SA 4.0",
         expires_h=24, trusted=False, default_on=True,
         includes=["adblock_suplement.txt", "adblock_ublock.txt"], kind="filters"),
    # lista domen w stylu DNS: telemetria telefonów/aplikacji/systemów (Xiaomi, Oppo, Huawei, Apple, Samsung…),
    # której listy przeglądarkowe nie obejmują; działa niezależnie od DNS w danej sieci (ok. 220 tys. domen,
    # w silniku ~1,5 MB pamięci). Wyjątki z ubo-unbreak ($badfilter) nadal ją poprawiają
    dict(id="hagezi-pro", title="HaGeZi Multi PRO – śledzenie i telemetria",
         desc="Domeny reklam, śledzenia i telemetrii urządzeń (telefony, aplikacje, systemy) – jak bloker DNS, "
              "ale w każdej sieci.",
         url="https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.txt",
         fallback="https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/pro.txt",
         homepage="https://github.com/hagezi/dns-blocklists", license="GPL-3.0", expires_h=24,
         trusted=False, default_on=True, includes=[], kind="filters"),
    dict(id="psl", title="Public Suffix List", desc="Lista sufiksów publicznych (rozpoznawanie domen).",
         url="https://publicsuffix.org/list/public_suffix_list.dat", fallback=None,
         homepage="https://publicsuffix.org/", license="MPL-2.0", expires_h=720, trusted=False, default_on=True,
         includes=[], kind="psl"),
]
BY_ID = {l["id"]: l for l in LISTS}
USER_ID = "user"            # "Moje filtry" (settings["adblock_user"]), never trusted


def get(list_id):
    return BY_ID.get(list_id)


def filter_lists():
    return [l for l in LISTS if l["kind"] == "filters"]


def enabled_ids(settings_map=None):
    """settings["adblock_lists"] ({id: bool}) merged over defaults; filter lists only, catalog order."""
    m = settings_map or {}
    return [l["id"] for l in filter_lists() if bool(m.get(l["id"], l["default_on"]))]


def include_url(lst, name):
    """URL of a same-directory !#include, or None when the name is not a plain file name."""
    if not safe_include_name(name):
        return None
    base = lst["url"].split("?", 1)[0]
    return base.rsplit("/", 1)[0] + "/" + name


def safe_include_name(name):
    return bool(name) and len(name) <= 128 and not any(c in name for c in '/\\:?#%') and ".." not in name \
        and not name.startswith(".")


# ---- storage ----
def root(home=None):
    return os.path.join(home or os.path.expanduser("~"), ".luna_adblock")


def lists_dir(home=None):
    return os.path.join(root(home), "lists")


def list_path(list_id, home=None):
    return os.path.join(lists_dir(home), list_id + ".txt")


def include_path(list_id, name, home=None):
    """<id>__<include file name> (e.g. pol0__adblock_ublock.txt)."""
    return os.path.join(lists_dir(home), "%s__%s" % (list_id, name))


def meta_path(home=None):
    return os.path.join(root(home), "meta.json")


def load_meta(home=None):
    try:
        with open(meta_path(home), encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def save_meta(meta, home=None):
    p = meta_path(home)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def is_expired(list_id, meta, now=None, home=None):
    """True when the list was never fetched, its file is missing, or fetched + expires_h has passed."""
    lst = BY_ID.get(list_id)
    if lst is None:
        return False
    m = meta.get(list_id) or {}
    fetched = m.get("fetched") or 0
    if not fetched or not os.path.isfile(list_path(list_id, home)):
        return True
    return (now or time.time()) >= fetched + lst["expires_h"] * 3600


def next_expiry(ids, meta, now=None):
    """Seconds until the earliest expiry among ids (>= 0), or None."""
    now = now or time.time()
    best = None
    for i in ids:
        lst = BY_ID.get(i)
        if not lst:
            continue
        t = ((meta.get(i) or {}).get("fetched") or 0) + lst["expires_h"] * 3600 - now
        best = t if best is None else min(best, t)
    return None if best is None else max(0.0, best)


def build_config(ids, user_text="", home=None):
    """config.json dict for compiler.main(): only lists whose file exists; includes = existing <id>__* files."""
    ldir = lists_dir(home)
    lists = []
    for i in ids:
        lst = BY_ID.get(i)
        if not lst or lst["kind"] != "filters":
            continue
        p = list_path(i, home)
        if not os.path.isfile(p):
            continue
        incs = [include_path(i, n, home) for n in lst["includes"] if os.path.isfile(include_path(i, n, home))]
        lists.append({"id": i, "path": p, "trusted": bool(lst["trusted"]), "includes": incs})
    pp = list_path("psl", home)
    return {"lists": lists, "user": user_text or "", "psl": pp if os.path.isfile(pp) else None,
            "lists_dir": ldir}
