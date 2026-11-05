"""Cosmetic filtering for Luna's ad blocker (DESIGN §6).

- static_script(cfg): profile-level world-7 engine (adblock/js/cosmetic.js) + generic config.
- host_data(entries, flags) / host_script(host, data): per-host data delivered to the engine.
- load(cos_bin_dict) + generic_lookup(tokens, host_unhide): answers the engine's `c?t=` lookups.

Pure stdlib; no Qt imports (the glue lives in adblock/__init__.py).
"""
import json
import os
from urllib.parse import parse_qs

WORLD_ID = 7
# NetEngine.page_flags bits
GHIDE, SHIDE, EHIDE, DOC = 1, 2, 4, 8

MAX_TOKENS = 4096          # per lookup request
MAX_TOKEN_LEN = 256

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_HERE, "js", "cosmetic.js")
_engine_src = None


def _dumps(obj):
    # ASCII-only JSON is a valid JS literal (no raw U+2028/2029)
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def engine_source():
    """Raw engine source (a single JS function expression)."""
    global _engine_src
    if _engine_src is None:
        with open(_ENGINE_PATH, encoding="utf-8") as f:
            _engine_src = f.read().strip()
    return _engine_src


# ---------------------------------------------------------------- generic data (cos.bin)
class _Generic:
    __slots__ = ("lowly", "high", "unhide")

    def __init__(self):
        self.lowly = {}
        self.high = []
        self.unhide = frozenset()


_G = _Generic()


def _as_list(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple)):
        return [s for s in v if isinstance(s, str) and s]
    return []


def load(cos):
    """Install generic cosmetics from the cos.bin dict ({"lowly", "high", "unhide"}). Returns stats."""
    g = _Generic()
    cos = cos if isinstance(cos, dict) else {}
    g.unhide = frozenset(_as_list(cos.get("unhide")))
    lowly = cos.get("lowly")
    if isinstance(lowly, dict):
        for k, v in lowly.items():
            if not isinstance(k, str):
                continue
            sels = [s for s in _as_list(v) if s not in g.unhide]
            if sels:
                g.lowly[k] = sels
    seen = set()
    for s in _as_list(cos.get("high")):
        if s not in g.unhide and s not in seen:
            seen.add(s)
            g.high.append(s)
    global _G
    _G = g
    return {"lowly_keys": len(g.lowly), "lowly": sum(len(v) for v in g.lowly.values()),
            "high": len(g.high), "unhide": len(g.unhide)}


def high_selectors():
    return list(_G.high)


def generic_unhide():
    return sorted(_G.unhide)


def parse_tokens(value):
    """`t` query value (already percent-decoded) -> list of ".cls"/"#id" tokens."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    out = []
    for t in (value or "").split(" "):
        if 1 < len(t) <= MAX_TOKEN_LEN and t[0] in ".#":
            out.append(t)
            if len(out) >= MAX_TOKENS:
                break
    return out


def generic_lookup(tokens, host_unhide=()):
    """Selectors of lowly generic filters keyed by the given tokens, minus generic and host exceptions."""
    lowly, gun = _G.lowly, _G.unhide
    hun = host_unhide if isinstance(host_unhide, (set, frozenset)) else set(host_unhide or ())
    out, seen = [], set()
    for t in tokens[:MAX_TOKENS]:
        sels = lowly.get(t)
        if not sels:
            continue
        for s in sels:
            if s not in seen and s not in gun and s not in hun:
                seen.add(s)
                out.append(s)
    return out


def lookup_json(query, host_unhide=()):
    """Scheme-handler helper: raw (percent-encoded) query string of `c?t=...` -> JSON body bytes.
    Pass QUrl.query(QUrl.ComponentFormattingOption.FullyEncoded) so '+' and '%2B' stay distinct."""
    if isinstance(query, bytes):
        query = query.decode("ascii", "replace")
    try:
        t = parse_qs(query or "", keep_blank_values=True).get("t", [""])[0]
    except Exception:
        t = ""
    return _dumps(generic_lookup(parse_tokens(t), host_unhide)).encode("ascii")


# ---------------------------------------------------------------- scripts
def static_script(cfg=None):
    """Profile-level world-7 script: engine + {sr, high, gen_unhide, allow}.
    Missing `high` / `gen_unhide` default to the data installed by load()."""
    cfg = dict(cfg or {})
    gen_unhide = _as_list(cfg.get("gen_unhide")) if "gen_unhide" in cfg else generic_unhide()
    gu = set(gen_unhide)
    high = _as_list(cfg.get("high")) if "high" in cfg else high_selectors()
    out = {
        "sr": cfg.get("sr") if isinstance(cfg.get("sr"), str) else "",
        "high": [s for s in high if s not in gu and "{" not in s and "}" not in s],
        "gen_unhide": gen_unhide,
        "allow": sorted({d.lower().strip(".") for d in _as_list(cfg.get("allow"))}),
    }
    return "(function(){try{(" + engine_source() + ")(" + _dumps(out) + ");}catch(e){}})();"


def host_script(host, data):
    """Guarded world-7 source delivering `data` (from host_data) to the engine on frames whose
    location.hostname == host (lower-case punycode)."""
    h = (host or "").lower()
    return ("(function(){if(location.hostname!==" + _dumps(h) + ")return;var d=" + _dumps(data or {}) +
            ",g=globalThis;if(typeof g.__lc===\"function\")g.__lc(d);else g.__lcq=d;})();")


def _rows(entries):
    for e in entries or ():
        if isinstance(e, (bytes, str)):
            try:
                e = json.loads(e)
            except Exception:
                continue
        if isinstance(e, dict):
            yield e


def host_data(entries, flags=0):
    """Merge site.db rows (dicts or JSON strings) for a host, apply #@# exceptions and page flags.
    Returns JSON-safe {"flags", "hide", "style", "remove", "proc", "unhide"} (empty keys omitted)."""
    flags = int(flags or 0)
    rows = list(_rows(entries))
    unhide = []
    for r in rows:
        unhide.extend(_as_list(r.get("unhide")))
    un = set(unhide)
    out = {"flags": flags}
    if flags & (EHIDE | DOC):
        return out
    if not flags & SHIDE:
        hide, style, remove, proc = [], [], [], []
        sh, ss, sr, sp = set(), set(), set(), set()
        for r in rows:
            for s in _as_list(r.get("hide")):
                if s not in un and s not in sh:
                    sh.add(s)
                    hide.append(s)
            for p in r.get("style") or ():
                if (isinstance(p, (list, tuple)) and len(p) == 2 and isinstance(p[0], str)
                        and isinstance(p[1], str) and p[0] and p[1]):
                    key = (p[0], p[1])
                    if key not in ss and f"{p[0]}:style({p[1]})" not in un:
                        ss.add(key)
                        style.append([p[0], p[1]])
            for s in _as_list(r.get("remove")):
                if s not in sr and f"{s}:remove()" not in un:
                    sr.add(s)
                    remove.append(s)
            for p in r.get("proc") or ():
                if not isinstance(p, dict) or not isinstance(p.get("t"), list):
                    continue
                key = p.get("s") if isinstance(p.get("s"), str) else _dumps(p)
                if key in un or key in sp:
                    continue
                sp.add(key)
                proc.append(p)
        for k, v in (("hide", hide), ("style", style), ("remove", remove), ("proc", proc)):
            if v:
                out[k] = v
    if un and not flags & GHIDE:
        out["unhide"] = sorted(un)     # engine subtracts these from generic selectors
    return out
