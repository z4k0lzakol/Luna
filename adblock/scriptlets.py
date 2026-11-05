"""Scriptlet bundle builder (main world). Pure stdlib, no Qt.

build(rules, host) -> JS source or None
    rules = [(canonical_name, [args...], trusted_source), ...]  (unjs exceptions already applied)
    Drops trusted-only scriptlets from untrusted sources, unknown/unimplemented names and duplicates.
    Output: one self-contained IIFE (no host guard, no sourceURL - the caller adds those).

Each implementation lives in adblock/js/scriptlets/<canonical-name>.js and contains exactly one
`function (R, ...args) { ... }` expression, optionally preceded by header comments:
    // @deps: other-name, other-name-2     (helpers reachable as R.deps["other-name"](R, ...))
    // @world: main
"""
import base64
import json
import os
import random
import re
import secrets

from .scriptlet_names import ALIASES, KNOWN, SUPPORTED, TRUSTED_ONLY, canonical, is_trusted_only  # noqa: F401

_HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(_HERE, "js")
SCRIPTLET_DIR = os.path.join(JS_DIR, "scriptlets")

# per-process secret for the runtime's private cross-realm channel (never shown to pages)
SECRET = secrets.token_hex(12)
# scheme base URL ("x<hex>://l/<token>/") exposed to scriptlets as R.SR; set by the glue via configure()
SR = ""

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MAX_ARG = 65536
_MAX_ARGS = 32
_cache = {}


def configure(sr=None):
    global SR
    if sr is not None:
        SR = str(sr)


def clear_cache():
    _cache.clear()


def _strip(src):
    """Light, safe minification: drop full-line // comments, leading indentation and blank lines."""
    out = []
    for line in src.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        out.append(s)
    return "\n".join(out)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def runtime_source():
    v = _cache.get(("rt",))
    if v is None:
        src = _strip(_read(os.path.join(JS_DIR, "runtime.js")))
        if not src.startswith("function"):
            raise ValueError("runtime.js must contain one function expression")
        v = _cache[("rt",)] = src
    return v


def _load(name):
    """-> (source, [deps]) or None if the scriptlet has no implementation file."""
    key = ("s", name)
    if key in _cache:
        return _cache[key]
    res = None
    if _NAME_RE.match(name or "") and ".." not in name:
        path = os.path.join(SCRIPTLET_DIR, name + ".js")
        if os.path.isfile(path):
            raw = _read(path)
            deps = []
            for line in raw.splitlines():
                s = line.strip()
                if not s:
                    continue
                if not s.startswith("//"):
                    break
                m = re.match(r"//\s*@deps:\s*(.*)$", s)
                if m:
                    deps += [d.strip() for d in m.group(1).split(",") if d.strip()]
            src = _strip(raw)
            if src.startswith("function"):
                res = (src, deps)
    _cache[key] = res
    return res


def available():
    """Canonical names that have an implementation file."""
    out = set()
    try:
        for fn in os.listdir(SCRIPTLET_DIR):
            if fn.endswith(".js") and _load(fn[:-3]):
                out.add(fn[:-3])
    except OSError:
        pass
    return out


def _js(s):
    # JSON string literal; ensure_ascii keeps U+2028/2029 and non-ASCII escaped
    return json.dumps(s, ensure_ascii=True)


_XMIME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*/[A-Za-z0-9][A-Za-z0-9.+-]*(?:;\s*charset=[A-Za-z0-9_-]+)?$")
_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_RNG = random.SystemRandom()


def fake_body(spec, method="GET"):
    """Body for the scheme path SR + "x/<spec>" (XHR fakes of prevent-xhr & co., encoding by SCRIPTLETS-1).

    spec = base64url (no padding) of UTF-8 JSON {"t": mime, "b": text} or {"t": mime, "n": length}
    ("n": that many random alphanumerics, <= 500000). Returns (mime, bytes) or None when invalid;
    HEAD gets an empty body. The glue replies with this mime (no other headers needed).
    """
    try:
        if not isinstance(spec, str) or len(spec) > 4 * 1024 * 1024:
            return None
        raw = spec.split("?", 1)[0].split("#", 1)[0]
        raw += "=" * (-len(raw) % 4)
        cfg = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
        if not isinstance(cfg, dict):
            return None
        mime = cfg.get("t", "text/plain")
        if not isinstance(mime, str) or not _XMIME.match(mime):
            return None
        if "n" in cfg:
            k = cfg["n"]
            if not isinstance(k, int) or isinstance(k, bool) or k < 0 or k > 500000:
                return None
            body = "".join(_RNG.choices(_ALNUM, k=k)).encode("ascii")
        else:
            b = cfg.get("b", "")
            if not isinstance(b, str) or len(b) > 2 * 1024 * 1024:
                return None
            body = b.encode("utf-8")
        if str(method).upper() == "HEAD":
            body = b""
        return mime, body
    except (ValueError, TypeError, UnicodeError):
        return None


def build(rules, host=None, sr=None):
    """rules: iterable of (name, args, trusted). Returns the JS bundle or None."""
    invocations = []
    seen = set()
    for rule in rules or ():
        try:
            name, args, trusted = rule[0], rule[1], bool(rule[2]) if len(rule) > 2 else False
        except (TypeError, IndexError):
            continue
        c = canonical(name)
        if c is None:
            continue
        if c in TRUSTED_ONLY and not trusted:
            continue
        if _load(c) is None:
            continue
        a = [str(x) for x in (args or ())][:_MAX_ARGS]
        if any(len(x) > _MAX_ARG for x in a):
            continue
        k = (c, tuple(a))
        if k in seen:
            continue
        seen.add(k)
        invocations.append(k)
    if not invocations:
        return None

    # resolve implementations (+ deps, depth-first, each once)
    order, ids = [], {}

    def need(nm, depth=0):
        if nm in ids or depth > 8:
            return nm in ids
        ld = _load(nm)
        if ld is None:
            return False
        for d in ld[1]:
            need(d, depth + 1)
        ids[nm] = "a%d" % len(order)
        order.append(nm)
        return True

    for c, _ in invocations:
        need(c)

    parts = ['(function(){"use strict";var M=', runtime_source(),
             ";var R=M(window,", _js(SR if sr is None else str(sr)), ",", _js(SECRET), ",null);\n"]
    for nm in order:
        parts.append("var %s=%s;\n" % (ids[nm], _load(nm)[0]))
    deps = sorted({d for nm in order for d in _load(nm)[1] if d in ids})
    parts.append("var D={%s};\n" % ",".join("%s:%s" % (_js(d), ids[d]) for d in deps))
    parts.append("R.boot(function(R){R.deps=D;\n")
    for c, a in invocations:
        parts.append("try{%s(R%s);}catch(e){}\n" % (ids[c], "".join("," + _js(x) for x in a)))
    parts.append("},M);})();")
    return "".join(parts)
