"""Filter-list compiler (runs in a subprocess, never in a thread of the GUI process).

CLI:  pythonw -I -c "import sys; sys.path.insert(0, r'<repo>'); from adblock import compiler; compiler.main()" \
          <lists_dir> <out_dir> <config.json>
config.json: {"lists": [{"id", "path", "trusted", "includes": [paths]}], "user": "<text>", "psl": "<path>|null"}
Output (<out_dir>, written to <out_dir>.tmp and renamed at the end):
  net.bin   marshal(netfilter.compile_network(items))   items = (text, list_id, trusted)
  cos.bin   marshal({"lowly": {".cls"|"#id": [sel]}, "high": [sel], "unhide": [sel]})   generic cosmetics
  site.db   sqlite3 table site(key TEXT PRIMARY KEY, data TEXT JSON)   per host / entity ("x.*") / ancestor (">>x")
            data fields: hide, unhide, style [[sel, decl]], remove, proc [AST], js [[name, args, trusted]],
            unjs [[name, args] | ["*"]]
            Extra (optional to use): /regex/ hostnames are stored under their raw text key ("/^x[.]com$/")
            and listed in the row with key "/" -> {"re": [keys]}; test them against location.hostname.
            Tip for readers: open with sqlite3.connect("file:<path>?mode=ro&immutable=1", uri=True)
            (about 6 us per lookup instead of about 90 us with the default locking mode).
  psl.bin   marshal(psl.parse(text)) when config "psl" is given (load with psl.PSL.load(path))
  info.json {"format": 1, "counts": {list_id: rules}, "total", "errors", "ms", "detail": {...}, "dropped": {...}}

Procedural cosmetic AST (site.db "proc" entries) - full description in adblock/PROC_AST.md:
  {"s": raw selector text (for #@# matching), "t": [task...], "a": action (absent = hide)}
  task:  ["css", sel] | ["spath", " > x"|" x"|" + x"|" ~ x"] | ["matches", compound] | ["has", [task...]]
         | ["not", [task...]] | ["has-text", pat] | ["min-text-length", n] | ["matches-attr", pat, pat|None]
         | ["matches-css", None|"before"|"after", prop, pat] | ["matches-media", query] | ["matches-path", pat]
         | ["matches-prop", chain, pat|None] | ["others"] | ["upward", n|sel] | ["watch-attr", [names]]
         | ["xpath", expr]
  pat:   {"r": regex source, "f": flags} | {"t": literal substring}
  action: ["style", decl] | ["remove"] | ["remove-attr", pat] | ["remove-class", pat]
"""
import json
import marshal
import os
import re
import shutil
import sqlite3
import sys
import time
import traceback

from . import psl as _psl

try:
    from . import scriptlet_names as _sn
except Exception:                                   # placeholder missing -> no alias resolution
    _sn = None

FORMAT = 1
MAX_LINE = 8192
MAX_FILE = 25 * 1024 * 1024
MAX_INCLUDE_DEPTH = 3

# ------------------------------------------------------------------------------------------------
# Preprocessor (!#if / !#else / !#endif / !#include)
# ------------------------------------------------------------------------------------------------
ENV_TRUE = frozenset(("ext_ublock", "env_chromium", "cap_user_stylesheet", "adguard_ext_chromium",
                      "adguard_ext_opera"))
_COND_TOK = re.compile(r"\s*(\(|\)|!|&&|\|\||[A-Za-z0-9_]+)")


def eval_cond(expr, env=ENV_TRUE):
    """!#if expression: tokens, !, &&, ||, parentheses. Unknown tokens / syntax errors -> False."""
    toks, pos, expr = [], 0, expr.strip()
    while pos < len(expr):
        m = _COND_TOK.match(expr, pos)
        if not m:
            if expr[pos:].strip() == "":
                break
            return False
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def peek():
        return toks[i] if i < len(toks) else None

    def p_or():
        nonlocal i
        v = p_and()
        while peek() == "||":
            i += 1
            v = p_and() or v
        return v

    def p_and():
        nonlocal i
        v = p_not()
        while peek() == "&&":
            i += 1
            v = p_not() and v
        return v

    def p_not():
        nonlocal i
        t = peek()
        if t == "!":
            i += 1
            return not p_not()
        if t == "(":
            i += 1
            v = p_or()
            if peek() == ")":
                i += 1
            return v
        i += 1
        return t in env

    try:
        v = bool(p_or())
        return v if i >= len(toks) else False
    except Exception:
        return False


def preprocess(text, load_include=None, stats=None, _depth=0):
    """Return active, stripped, non-empty lines. load_include(name) -> text|None (same-dir names only)."""
    out = []
    stack = []                          # [cond_value, parent_active]
    active = True
    if text.startswith("\ufeff"):
        text = text[1:]
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line[0] == "!" and line.startswith("!#"):
            if line.startswith("!#if") and (len(line) == 4 or line[4] in " \t("):
                v = eval_cond(line[4:])
                stack.append([v, active])
                active = active and v
                continue
            if line.startswith("!#else"):
                if stack:
                    v, parent = stack[-1]
                    stack[-1][0] = not v
                    active = parent and not v
                continue
            if line.startswith("!#endif"):
                if stack:
                    active = stack.pop()[1]
                continue
            if line.startswith("!#include"):
                if active and load_include is not None and _depth < MAX_INCLUDE_DEPTH:
                    name = line[9:].strip()
                    sub = load_include(name)
                    if sub is not None:
                        if stats is not None:
                            stats["includes"] = stats.get("includes", 0) + 1
                        out.extend(preprocess(sub, load_include, stats, _depth + 1))
                    elif stats is not None:
                        stats["include_missing"] = stats.get("include_missing", 0) + 1
                continue
            continue                    # other directives (!#safari_cb_affinity ...)
        if active:
            out.append(line)
        elif stats is not None:
            stats["pre_skipped"] = stats.get("pre_skipped", 0) + 1
    return out


def _safe_include_name(name):
    return bool(name) and len(name) <= 128 and not any(c in name for c in '/\\:?#%') and ".." not in name \
        and not name.startswith(".")


# ------------------------------------------------------------------------------------------------
# Hostnames
# ------------------------------------------------------------------------------------------------
_HOST_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_.-]*[a-z0-9_])?$")


def norm_host(h):
    """lower-case punycode hostname, trailing dot removed; None when invalid."""
    h = h.strip().lower().rstrip(".")
    if not h:
        return None
    if not h.isascii():
        try:
            h = h.encode("idna").decode("ascii")
        except Exception:
            return None
    if h.startswith("[") and h.endswith("]"):
        return h
    if ".." in h or not _HOST_RE.match(h):
        return None
    return h


def split_domains(s, sep=","):
    """Split a hostname list on sep without splitting inside /regex/ entries."""
    toks, i, n = [], 0, len(s)
    while i < n:
        start = i
        j = i + 1 if s[i] == "~" else i
        if j < n and s[j] == "/":
            k = j + 1
            while k < n:
                if s[k] == "\\":
                    k += 2
                    continue
                if s[k] == "/" and (k + 1 >= n or s[k + 1] == sep):
                    break
                k += 1
            toks.append(s[start:k + 1])
            i = k + 2
        else:
            k = s.find(sep, i)
            if k < 0:
                k = n
            toks.append(s[start:k])
            i = k + 1
    return [t.strip() for t in toks if t.strip()]


def parse_hosts(prefix):
    """-> (pos keys, neg keys, ancestor keys, n_bad, has_star). Keys: host, 'name.*', ancestors as '>>host'."""
    pos, neg, anc = [], [], []
    bad = 0
    star = False
    for tok in split_domains(prefix):
        is_neg = tok[0] == "~"
        t = tok[1:].strip() if is_neg else tok
        if not t:
            bad += 1
            continue
        if t[0] == "/":
            # /regex/ hostname: kept as its own site.db key (raw text), listed in row "/" -> {"re": [...]}
            if is_neg or len(t) < 3 or not t.endswith("/") or len(t) > 512:
                bad += 1
            else:
                pos.append(t)
            continue
        is_anc = t.endswith(">>")
        if is_anc:
            t = t[:-2]
        if t == "*":
            if not is_neg and not is_anc:
                star = True
            else:
                bad += 1
            continue
        if t.endswith(".*"):
            h = norm_host(t[:-2])
            key = h + ".*" if h else None
        else:
            key = norm_host(t)
        if not key:
            bad += 1
            continue
        if is_anc:
            if is_neg:
                bad += 1
            else:
                anc.append(">>" + key)
        elif is_neg:
            neg.append(key)
        else:
            pos.append(key)
    return pos, neg, anc, bad, star


# ------------------------------------------------------------------------------------------------
# Selector scanning helpers
# ------------------------------------------------------------------------------------------------
class Invalid(ValueError):
    pass


class Unsupported(ValueError):
    pass


_OPS = frozenset((
    "has", "-abp-has", "if", "not", "if-not", "has-text", "contains", "-abp-contains", "matches-attr",
    "matches-css", "matches-css-before", "matches-css-after", "matches-media", "matches-path", "matches-prop",
    "matches-property", "min-text-length", "nth-ancestor", "others", "upward", "watch-attr", "xpath",
    "style", "remove", "remove-attr", "remove-class", "-abp-properties"))
_ACTIONS = frozenset(("style", "remove", "remove-attr", "remove-class"))
_GATES = frozenset(("matches-path", "matches-media", "watch-attr"))
_FUNC_RE = re.compile(r":(-?[A-Za-z][A-Za-z0-9-]*)\(")
_PROC_HINT = re.compile(r":(?:-abp-|has-text|contains|if|matches-|min-text|nth-ancestor|others|upward|"
                        r"watch-attr|xpath|style|remove)")


def _skip_quote(s, i):
    """s[i] is a quote; return index after the closing quote, or -1 when unterminated."""
    q, n, j = s[i], len(s), i + 1
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == q:
            return j + 1
        j += 1
    return -1


def _scan_regex(s, j):
    """s[j] == '/'; return index after '/regex/flags' or -1."""
    n, k, cls = len(s), j + 1, False
    while k < n:
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if cls:
            if c == "]":
                cls = False
        elif c == "[":
            cls = True
        elif c == "/":
            if k == j + 1:
                return -1
            k += 1
            while k < n and s[k].isalpha():
                k += 1
            return k
        k += 1
    return -1


def _find_close(s, i):
    """s[i-1] == '('; index of the matching ')' or -1. Skips quotes, escapes and a leading /regex/."""
    n = len(s)
    j = i
    while j < n and s[j] in " \t":
        j += 1
    if j < n and s[j] == "/":
        k = _scan_regex(s, j)
        if k > 0:
            while k < n and s[k] in " \t":
                k += 1
            if k < n and s[k] == ")":
                return k
    depth = 1
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c in "\"'":
            k = _skip_quote(s, i)
            if k > 0:
                i = k
                continue
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _find_bracket(s, i):
    """s[i] == '['; index of matching ']' or -1."""
    n, j = len(s), i + 1
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c in "\"'":
            k = _skip_quote(s, j)
            if k < 0:
                return -1
            j = k
            continue
        if c == "]":
            return j
        j += 1
    return -1


def segments(s):
    """Split a selector into [("css", text) | ("op", name, arg)] at nesting depth 0."""
    out, buf, i, n = [], [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            buf.append(s[i:i + 2])
            i += 2
            continue
        if c == "[":
            k = _find_bracket(s, i)
            if k < 0:
                raise Invalid("bracket")
            buf.append(s[i:k + 1])
            i = k + 1
            continue
        if c in "\"'":
            k = _skip_quote(s, i)
            if k < 0:
                raise Invalid("quote")
            buf.append(s[i:k])
            i = k
            continue
        if c == "(":
            k = _find_close(s, i + 1)
            if k < 0:
                raise Invalid("paren")
            buf.append(s[i:k + 1])
            i = k + 1
            continue
        if c == ")" or c == "]":
            raise Invalid("unbalanced")
        if c == ":":
            m = _FUNC_RE.match(s, i)
            if m:
                name = m.group(1).lower()
                k = _find_close(s, m.end())
                if k < 0:
                    raise Invalid("paren")
                arg = s[m.end():k]
                if name in _OPS:
                    if buf:
                        out.append(("css", "".join(buf)))
                        buf = []
                    out.append(("op", name, arg))
                else:
                    if _PROC_HINT.search(arg) and _has_proc(arg):
                        raise Unsupported("procedural inside :%s()" % name)
                    buf.append(s[i:k + 1])
                i = k + 1
                continue
        buf.append(c)
        i += 1
    if buf:
        out.append(("css", "".join(buf)))
    return out


def _has_proc(s):
    try:
        segs = segments(s)
    except Unsupported:
        return True
    except Invalid:
        return False
    for sg in segs:
        if sg[0] == "op" and sg[1] not in ("has", "not"):
            return True
        if sg[0] == "op" and _has_proc(sg[2]):
            return True
    return False


def _native_arg(arg, in_has):
    """True when arg (of :has/:not) is plain CSS that Chromium accepts natively."""
    for sg in segments(arg):
        if sg[0] == "css":
            if in_has and ":scope" in sg[1]:
                return False
            continue
        name = sg[1]
        if name in ("has", "-abp-has", "if"):
            if in_has or ":scope" in sg[2] or not _native_arg(sg[2], True):
                return False
        elif name == "not":
            if not _native_arg(sg[2], in_has):
                return False
        else:
            return False
    return True


def _rebuild(segs):
    """Native-only segments -> CSS text (:-abp-has/:if -> :has)."""
    out = []
    for sg in segs:
        if sg[0] == "css":
            out.append(sg[1])
        elif sg[1] in ("has", "-abp-has", "if"):
            out.append(":has(" + _rebuild(segments(sg[2])) + ")")
        else:
            out.append(":not(" + _rebuild(segments(sg[2])) + ")")
    return "".join(out)


def valid_css(sel):
    """Contract check: no { } ; outside quotes, no leading @, no /*, balanced quotes/brackets/parens."""
    sel = sel.strip()
    if not sel or sel[0] == "@" or "/*" in sel:
        return False
    depth_b = depth_p = 0
    i, n = 0, len(sel)
    while i < n:
        c = sel[i]
        if c == "\\":
            i += 2
            continue
        if c in "\"'":
            k = _skip_quote(sel, i)
            if k < 0:
                return False
            i = k
            continue
        if c in "{};":
            return False
        if c == "[":
            depth_b += 1
        elif c == "]":
            depth_b -= 1
            if depth_b < 0:
                return False
        elif c == "(":
            depth_p += 1
        elif c == ")":
            depth_p -= 1
            if depth_p < 0:
                return False
        i += 1
    return depth_b == 0 and depth_p == 0


_BAD_DECL = ("url(", "image-set(", "@import", "expression", "\\", "/*", "*/", "//", "{", "}", "javascript:",
             "-moz-binding", "behavior:", "<")


def sanitize_decl(decl):
    d = decl.strip()
    low = d.lower()
    if not d or any(b in low for b in _BAD_DECL):
        raise Invalid("style")
    if re.search(r"/\s*/", d):
        raise Invalid("style")
    return d


def _mask(s):
    """Same length; content of quotes, [] and () replaced by '_' (delimiters kept)."""
    out = list(s)
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c in "\"'":
            k = _skip_quote(s, i)
            k = n if k < 0 else k
            for j in range(i + 1, max(i + 1, k - 1)):
                out[j] = "_"
            i = k
            continue
        if c in "[(":
            k = _find_bracket(s, i) if c == "[" else _find_close(s, i + 1)
            k = n - 1 if k < 0 else k
            for j in range(i + 1, k):
                out[j] = "_"
            i = k + 1
            continue
        i += 1
    return "".join(out)


def split_top(sel, sep=","):
    m = _mask(sel)
    parts, start = [], 0
    for i, c in enumerate(m):
        if c == sep:
            parts.append(sel[start:i].strip())
            start = i + 1
    parts.append(sel[start:].strip())
    return [p for p in parts if p]


_TOKEN_RE = re.compile(r"([#.])(-?[A-Za-z_][A-Za-z0-9_-]*)")


def lowly_key(sel):
    """'.cls' / '#id' from the rightmost compound of a generic selector, or None (-> high)."""
    m = _mask(sel)
    start = 0
    for i in range(len(m) - 1, -1, -1):
        if m[i] in " >+~\t":
            start = i + 1
            break
    comp = m[start:]
    best = None
    for t in _TOKEN_RE.finditer(comp):
        end = start + t.end()
        if end < len(sel) and sel[end] == "\\":
            continue
        k = t.group(1) + t.group(2)
        if t.group(1) == "#":
            return k
        if best is None:
            best = k
    return best


# ------------------------------------------------------------------------------------------------
# Procedural selector -> AST
# ------------------------------------------------------------------------------------------------
_COMB = " >+~\t\n"


def _js_escape(lit):
    return "".join("\\" + c if c in "\\^$.|?*+()[]{}/" else c for c in lit)


def _unquote(a):
    if len(a) >= 2 and a[0] in "\"'" and a[-1] == a[0]:
        q = a[0]
        return a[1:-1].replace("\\" + q, q).replace("\\\\", "\\"), True
    return a, False


_RE_LIT = re.compile(r"/(.+)/([A-Za-z]*)", re.S)


def parse_pat(arg):
    a = arg.strip()
    lit, quoted = _unquote(a)
    if quoted:
        return {"t": lit}
    m = _RE_LIT.fullmatch(a)
    if m:
        return {"r": m.group(1), "f": "".join(c for c in m.group(2) if c in "imsu")}
    return {"t": a}


def _exact_pat(arg, wildcard=False):
    """Literal -> anchored exact regex ('*' wildcard optional); /re/ (also quoted "/re/") -> regex."""
    p = parse_pat(arg)
    if "r" in p:
        return p
    t = p["t"]
    m = _RE_LIT.fullmatch(t)
    if m:
        return {"r": m.group(1), "f": "".join(c for c in m.group(2) if c in "imsu")}
    if not t:
        raise Invalid("empty")
    src = _js_escape(t)
    if wildcard:
        src = src.replace("\\*", ".*")
    return {"r": "^" + src + "$", "f": ""}


def _norm_comb(text):
    """' >  a b' -> ' > a b' ; ' a' -> ' a' ; '+a' -> ' + a'."""
    t = text.lstrip()
    if t and t[0] in ">+~":
        return " " + t[0] + " " + t[1:].lstrip()
    return " " + t


def _split_compound(text):
    """'.foo > a' -> ('.foo', ' > a'); '.foo' -> ('.foo', '')."""
    m = _mask(text)
    for i, c in enumerate(m):
        if c in _COMB:
            return text[:i], text[i:]
    return text, ""


def _css_frag_ok(frag):
    f = frag.strip()
    if f and f[0] in ">+~":
        f = "*" + f
    if not valid_css(f):
        raise Invalid("css")


def build_chain(segs, mode, forced=False):
    """mode: 'top' | 'has' | 'not'. Returns task list (action ops must have been removed)."""
    # merge native :has()/:not() into neighbouring css text
    merged = []
    for sg in segs:
        if sg[0] == "op":
            name = sg[1]
            native = False
            if name in ("has", "-abp-has", "if") and not (forced and mode == "top"):
                native = ":scope" not in sg[2] and _native_arg(sg[2], True)
            elif name == "not":
                native = _native_arg(sg[2], False)
            if native:
                txt = _rebuild([sg])
                if merged and merged[-1][0] == "css":
                    merged[-1] = ("css", merged[-1][1] + txt)
                else:
                    merged.append(("css", txt))
                continue
            merged.append(sg)
        elif merged and merged[-1][0] == "css":
            merged[-1] = ("css", merged[-1][1] + sg[1])
        else:
            merged.append(sg)

    tasks = []
    selecting = False
    root_gate = 0

    def emit_css(text):
        nonlocal selecting
        if mode == "top" and not selecting:
            t = text.strip()
            if not t:
                return
            if t[0] in ">+~":
                raise Invalid("leading combinator")
            _css_frag_ok(t)
            tasks.append(["css", t])
            selecting = True
            return
        if not tasks and mode == "has":
            t = text.strip()
            if not t:
                return
            if t[0] in ">+~":
                t = t[0] + " " + t[1:].lstrip()
            _css_frag_ok(t)
            tasks.append(["css", t])
            return
        if not tasks and mode == "not":
            t = text.strip()
            if not t:
                return
            if t[0] in ">+~":
                t = t[0] + " " + t[1:].lstrip()
                _css_frag_ok(t)
                tasks.append(["has", [["css", t]]])
                return
            comp, rest = _split_compound(t)
            _css_frag_ok(comp)
            tasks.append(["matches", comp])
            if rest.strip():
                sp = _norm_comb(rest)
                _css_frag_ok(sp)
                tasks.append(["spath", sp])
            return
        if not text.strip():
            return
        if text[0] in _COMB:
            sp = _norm_comb(text)
            _css_frag_ok(sp)
            tasks.append(["spath", sp])
        else:
            comp, rest = _split_compound(text)
            _css_frag_ok(comp)
            tasks.append(["matches", comp])
            if rest.strip():
                sp = _norm_comb(rest)
                _css_frag_ok(sp)
                tasks.append(["spath", sp])

    last = len(merged) - 1
    for idx, sg in enumerate(merged):
        if sg[0] == "css":
            text = sg[1]
            if not text.strip() and idx != last and (selecting or tasks or mode != "top"):
                text = text + "*"                  # 'a:has-text(x) :upward(1)' -> descendant any
            emit_css(text)
            continue
        name, arg = sg[1], sg[2]
        if name in _ACTIONS:
            raise Invalid("action not last")
        if mode == "top" and not selecting and name not in _GATES:
            if name == "xpath":
                selecting = True
            else:
                t = _op_task(name, arg, forced)
                if name == "not" and all(x[0] in _GATES for x in t[1]):
                    # ':not(:matches-path(x)) sel' = negated page gate: root the chain at <html>
                    tasks.extend([["css", "html"], t])
                    root_gate = len(tasks)
                    selecting = True
                    continue
                tasks.append(["css", "*"])
                selecting = True
        tasks.append(_op_task(name, arg, forced))
    if mode == "top" and not selecting:
        raise Invalid("no subject")
    if mode == "top" and root_gate and all(x[0] in _GATES for x in tasks[root_gate:]):
        raise Invalid("no subject")             # would hide <html>
    if not tasks:
        raise Invalid("empty")
    return tasks


def _op_task(name, arg, forced):
    a = arg.strip()
    if name in ("has", "-abp-has", "if"):
        return ["has", build_chain(segments(a), "has")]
    if name == "not":
        return ["not", build_chain(segments(a), "not")]
    if name == "if-not":
        return ["not", [["has", build_chain(segments(a), "has")]]]
    if name in ("has-text", "contains", "-abp-contains"):
        return ["has-text", parse_pat(a)]
    if name in ("matches-css", "matches-css-before", "matches-css-after"):
        pseudo = None if name == "matches-css" else name[12:]
        prop, sep, val = a.partition(":")
        prop = prop.strip().lower()
        if not sep or not prop or not val.strip():
            raise Invalid("matches-css")
        return ["matches-css", pseudo, prop, parse_pat(val)]
    if name == "matches-attr":
        if not a:
            raise Invalid("matches-attr")
        if a[0] in "\"'":
            k = _skip_quote(a, 0)
            if k < 0:
                raise Invalid("matches-attr")
            nm, rest = a[:k], a[k:].strip()
        else:
            nm, eq, rest = a.partition("=")
            rest = ("=" + rest) if eq else ""
        rest = rest.strip()
        npat = _exact_pat(nm.strip(), True)
        if rest:
            if rest[0] != "=":
                raise Invalid("matches-attr")
            vpat = _exact_pat(rest[1:].strip(), True) if rest[1:].strip() not in ('""', "''") \
                else {"r": "^$", "f": ""}
        else:
            vpat = None
        return ["matches-attr", npat, vpat]
    if name == "matches-media":
        if not a or any(c in a for c in "{};"):
            raise Invalid("matches-media")
        return ["matches-media", a]
    if name == "matches-path":
        if not a:
            raise Invalid("matches-path")
        return ["matches-path", parse_pat(a)]
    if name in ("matches-prop", "matches-property"):
        chain, eq, val = a.partition("=")
        chain = chain.strip()
        if not chain or not re.fullmatch(r"[A-Za-z0-9_$.\[\]-]+", chain):
            raise Invalid("matches-prop")
        return ["matches-prop", chain, _exact_pat(val.strip()) if eq else None]
    if name == "min-text-length":
        if not a.isdigit():
            raise Invalid("min-text-length")
        return ["min-text-length", int(a)]
    if name in ("upward", "nth-ancestor"):
        if a.isdigit():
            n = int(a)
            if not 1 <= n <= 255:
                raise Invalid("upward")
            return ["upward", n]
        if name == "nth-ancestor" or not a or not valid_css(a) or _has_proc(a):
            raise Invalid("upward")
        return ["upward", a]
    if name == "watch-attr":
        names = [x.strip() for x in _unquote(a)[0].split(",") if x.strip()]
        return ["watch-attr", names]
    if name == "xpath":
        if not a:
            raise Invalid("xpath")
        return ["xpath", a]
    if name == "others":
        if a:
            raise Invalid("others")
        return ["others"]
    raise Unsupported(name)


def _action(name, arg):
    a = arg.strip()
    if name == "style":
        return ["style", sanitize_decl(a)]
    if name == "remove":
        if a:
            raise Invalid("remove")
        return ["remove"]
    return [name, _exact_pat(a)]


def compile_selector(raw, forced=False):
    """Returns ("hide", css) | ("style", css, decl) | ("remove", css) | ("proc", ast).
    Raises Invalid / Unsupported."""
    sel = raw.strip()
    if not sel or len(sel) > 4096:
        raise Invalid("empty")
    segs = segments(sel)
    action = None
    if segs and segs[-1][0] == "op" and segs[-1][1] in _ACTIONS:
        action = _action(segs[-1][1], segs[-1][2])
        segs = segs[:-1]
        if not segs:
            raise Invalid("action only")
    for sg in segs:
        if sg[0] == "op" and sg[1] == "-abp-properties":
            raise Unsupported("-abp-properties")
    native = True
    for sg in segs:
        if sg[0] == "op":
            if sg[1] in ("has", "-abp-has", "if") and not forced:
                if ":scope" in sg[2] or not _native_arg(sg[2], True):
                    native = False
            elif sg[1] == "not":
                if not _native_arg(sg[2], False):
                    native = False
            else:
                native = False
        if not native:
            break
    if native and not forced:
        css = _rebuild(segs).strip()
        if not valid_css(css):
            raise Invalid("css")
        if action is None:
            return ("hide", css)
        if action[0] == "style":
            return ("style", css, action[1])
        if action[0] == "remove":
            return ("remove", css)
        return ("proc", {"s": sel, "t": [["css", css]], "a": action})
    tasks = build_chain(segs, "top", forced)
    ast = {"s": sel, "t": tasks}
    if action is not None:
        ast["a"] = action
    return ("proc", ast)


def css_injection(body):
    """'sel { decl }' -> 'sel:style(decl)'; '{ remove: true; }' -> 'sel:remove()'; None when not that form."""
    body = body.strip()
    if not body.endswith("}"):
        return None
    m = _mask(body)
    i = m.find("{")
    if i <= 0:
        return None
    sel, decl = body[:i].strip(), body[i + 1:-1].strip()
    if not sel or not decl or "{" in decl or "}" in decl:
        return None
    if re.fullmatch(r"remove\s*:\s*true\s*;?", decl, re.I):
        return sel + ":remove()"
    return "%s:style(%s)" % (sel, decl)


def ident(res):
    """Text an #@# exception must equal to cancel this compiled cosmetic."""
    k = res[0]
    if k == "hide":
        return res[1]
    if k == "style":
        return "%s:style(%s)" % (res[1], res[2])
    if k == "remove":
        return res[1] + ":remove()"
    return res[1]["s"]


# ------------------------------------------------------------------------------------------------
# Scriptlets
# ------------------------------------------------------------------------------------------------
def split_args(body):
    """+js() argument splitting (spec 01 section 3)."""
    out, i, n = [], 0, len(body)
    while True:
        while i < n and body[i] in " \t":
            i += 1
        if i >= n:
            if out:
                out.append("")
            break
        c = body[i]
        if c in "'\"`":
            j, buf, closed = i + 1, [], False
            while j < n:
                if body[j] == "\\" and j + 1 < n and body[j + 1] == c:
                    buf.append(c)
                    j += 2
                    continue
                if body[j] == c:
                    closed = True
                    j += 1
                    break
                buf.append(body[j])
                j += 1
            k = j
            while k < n and body[k] in " \t":
                k += 1
            if closed and (k >= n or body[k] == ","):
                out.append("".join(buf))
                if k >= n:
                    break
                i = k + 1
                if i >= n:
                    out.append("")
                    break
                continue
        buf, j = [], i
        while j < n:
            if body[j] == "\\" and j + 1 < n and body[j + 1] == ",":
                buf.append(",")
                j += 2
                continue
            if body[j] == ",":
                break
            buf.append(body[j])
            j += 1
        out.append("".join(buf).rstrip(" \t"))
        if j >= n:
            break
        i = j + 1
        if i >= n:
            out.append("")
            break
    return out


def _sn_tables():
    """(aliases, trusted_only, known). known = every name worth keeping in site.db: KNOWN when the table
    exists (so a build stays valid when more scriptlet implementations ship), else SUPPORTED; empty = keep all."""
    if _sn is None:
        return {}, set(), set()
    known = set(getattr(_sn, "KNOWN", ()) or ()) or set(getattr(_sn, "SUPPORTED", ()) or ())
    return (getattr(_sn, "ALIASES", {}) or {}, set(getattr(_sn, "TRUSTED_ONLY", ()) or ()), known)


def canonical_name(name, aliases):
    n = name.strip()
    fn = getattr(_sn, "canonical", None) if _sn is not None else None
    if fn is not None:
        try:
            c = fn(n)
        except Exception:
            c = None
        if c:
            return c
    if n.startswith("ubo-"):
        n = n[4:]
    if n.endswith(".js"):
        n = n[:-3]
    return aliases.get(n, n)


# ------------------------------------------------------------------------------------------------
# Line classification + builder
# ------------------------------------------------------------------------------------------------
_COS_SEP = re.compile(r"#@?(?:\?|\$\??|%)?#|\$@?\$")
_HOSTS_LINE = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1|0|::1?)\s+(.+)$")
_HOSTS_SKIP = {"localhost", "localhost.localdomain", "local", "broadcasthost", "0.0.0.0", "ip6-localhost",
               "ip6-loopback"}


class Builder:
    def __init__(self):
        self.site = {}                  # key -> {field: {dedupe_key: value}}
        self.lowly = {}
        self.high = {}
        self.gunhide = {}
        self.net = []
        self.counts = {}
        self.detail = {}
        self.dropped = {}
        self.errors = 0
        self.re_keys = []
        self.aliases, self.trusted_only, self.supported = _sn_tables()

    # -- helpers --
    def _drop(self, why):
        self.dropped[why] = self.dropped.get(why, 0) + 1

    def _ok(self, list_id, kind):
        self.counts[list_id] = self.counts.get(list_id, 0) + 1
        d = self.detail.setdefault(list_id, {})
        d[kind] = d.get(kind, 0) + 1

    def _entry(self, key):
        e = self.site.get(key)
        if e is None:
            e = self.site[key] = {}
            if key[0] == "/":
                self.re_keys.append(key)
        return e

    def _put(self, key, field, dkey, value):
        e = self.site.get(key)
        if e is None:
            e = self._entry(key)
        f = e.get(field)
        if f is None:
            f = e[field] = {}
        if dkey not in f:
            f[dkey] = value

    # -- entry point --
    def add(self, line, list_id, trusted):
        if len(line) > MAX_LINE:
            self._drop("line_too_long")
            return
        c0 = line[0]
        if c0 == "!":
            return
        if c0 == "[":
            if line.startswith(("[Adblock", "[uBlock", "[AdGuard")):
                return
            if line.startswith("[$"):
                self._drop("adguard_modifier")
                return
        if c0 in "0123:" and (c0 != "1" or line.startswith("127.0.0.1")):
            m = _HOSTS_LINE.match(line)
            if m:
                self._hosts(m.group(1), list_id, trusted)
                return
        if c0 == "|" or line.startswith("@@"):
            self.net.append((line, list_id, trusted))
            self._ok(list_id, "net")
            return
        if "#" in line or "$$" in line or "$@$" in line:
            m = _COS_SEP.search(line)
            if m:
                prefix = line[:m.start()]
                if not prefix or (" " not in prefix and "\t" not in prefix and (
                        not any(ch in prefix for ch in "|^@\"'")
                        or prefix[0] == "/" or prefix.startswith("~/") or ",/" in prefix or ",~/" in prefix)):
                    if c0 == "#" and m.start() != 0:
                        return                      # '# comment' (hosts files)
                    self._cosmetic(prefix, m.group(0), line[m.end():], list_id, trusted)
                    return
            if c0 == "#":
                return                              # hosts-style comment
        self.net.append((line, list_id, trusted))
        self._ok(list_id, "net")

    def _hosts(self, rest, list_id, trusted):
        rest = rest.split("#", 1)[0]
        for h in rest.split():
            if h in _HOSTS_SKIP:
                continue
            k = norm_host(h)
            if not k or "." not in k:
                self._drop("hosts_invalid")
                continue
            self.net.append(("||" + k + "^", list_id, trusted))
            self._ok(list_id, "hosts")

    def _cosmetic(self, prefix, sep, body, list_id, trusted):
        body = body.strip()
        if not body:
            self.errors += 1
            return
        if sep in ("$$", "$@$"):
            self._drop("html_filter")
            return
        if "%" in sep:
            self._drop("adguard_js")
            return
        exc = "@" in sep
        forced = "?" in sep
        if "$" in sep or (body[-1] == "}" and "{" in body and not body.startswith("+js(")):
            conv = css_injection(body)              # AdGuard #$# / ABP '##sel {decl}' -> :style() / :remove()
            if conv is None and "$" in sep:
                self.errors += 1
                self._drop("css_injection_invalid")
                return
            if conv is not None:
                body = conv
                self.detail.setdefault(list_id, {})["css_injection"] = \
                    self.detail.get(list_id, {}).get("css_injection", 0) + 1
        if prefix:
            pos, neg, anc, bad, star = parse_hosts(prefix)
            if bad:
                self._drop("bad_hostname")
            if bad and not pos and not neg and not anc and not star:
                return
        else:
            pos, neg, anc, star = [], [], [], False
        if not forced and body.startswith("+js(") and sep in ("##", "#@#"):
            self._scriptlet(body, exc, pos, neg, anc, star, list_id, trusted)
            return
        if body[0] == "^":
            self._drop("html_filter")
            return
        if anc:
            self._drop("cos_ancestor")
            anc = []
            if not pos and not star:
                return
        if exc:
            self._cos_exception(body, forced, pos, neg, star, list_id)
            return
        try:
            res = compile_selector(body, forced)
        except Unsupported:
            self._drop("cos_unsupported")
            return
        except (Invalid, RecursionError):
            self.errors += 1
            self._drop("cos_invalid")
            return
        generic = star or not pos
        if generic:
            if res[0] != "hide":
                self._drop("generic_procedural")
                return
            pieces = split_top(res[1]) if not star else [res[1]]
            for p in pieces:
                if star:
                    self.high.setdefault(p, None)
                    continue
                k = lowly_key(p)
                if k is None:
                    self.high.setdefault(p, None)
                else:
                    self.lowly.setdefault(k, {}).setdefault(p, None)
            for h in neg:
                for p in pieces:
                    self._put(h, "unhide", p, p)
            for h in pos:                     # '*,example.com##x' -> already generic
                pass
            self._ok(list_id, "generic")
            return
        kind = res[0]
        idt = ident(res)
        for h in pos:
            if kind == "hide":
                self._put(h, "hide", res[1], res[1])
            elif kind == "style":
                self._put(h, "style", idt, [res[1], res[2]])
            elif kind == "remove":
                self._put(h, "remove", res[1], res[1])
            else:
                self._put(h, "proc", idt, res[1])
        for h in neg:
            self._put(h, "unhide", idt, idt)
        self._ok(list_id, "specific")

    def _cos_exception(self, body, forced, pos, neg, star, list_id):
        texts = [body]
        try:
            res = compile_selector(body, forced)
            t = ident(res)
            if t != body:
                texts.append(t)
        except (Invalid, Unsupported, RecursionError):
            res = None
        if not pos or star:
            if neg and not pos and not star:
                self._drop("cos_exception_negated_only")
                return
            pieces = []
            for t in texts:
                pieces.extend(split_top(t) if res is not None and res[0] == "hide" else [t])
            for p in pieces:
                self.gunhide.setdefault(p, None)
            self._ok(list_id, "generic_unhide")
            return
        for h in pos:
            for t in texts:
                self._put(h, "unhide", t, t)
        self._ok(list_id, "unhide")

    def _scriptlet(self, body, exc, pos, neg, anc, star, list_id, trusted):
        if not body.endswith(")"):
            self.errors += 1
            self._drop("js_invalid")
            return
        inner = body[4:-1]
        keys = pos + anc
        if not inner.strip():
            if not exc:
                self._drop("js_empty")
                return
            if not keys:
                self._drop("unjs_generic")
                return
            for h in keys:
                self._put(h, "unjs", "*", ["*"])
            self._ok(list_id, "unjs")
            return
        args = split_args(inner)
        name = canonical_name(args[0], self.aliases)
        args = args[1:]
        if not name:
            self.errors += 1
            self._drop("js_invalid")
            return
        dk = json.dumps([name, args], ensure_ascii=False)
        if exc:
            if not keys:
                self._drop("unjs_generic")
                return
            for h in keys:
                self._put(h, "unjs", dk, [name, args])
            self._ok(list_id, "unjs")
            return
        if not keys:
            self._drop("js_generic")
            return
        if (name.startswith("trusted-") or name in self.trusted_only) and not trusted:
            self._drop("js_untrusted")
            return
        if self.supported and name not in self.supported:
            self._drop("js_unknown")
            return
        if name in ("set-attr", "trusted-set-attr") and len(args) >= 2 and \
                any(a.strip().lower().startswith("on") for a in args[1].split("|")):
            self._drop("js_unsafe")
            return
        if any("javascript:" in a.lower() for a in args) and name in ("set-attr", "trusted-set-attr",
                                                                          "href-sanitizer"):
            self._drop("js_unsafe")
            return
        for h in keys:
            e = self._entry(h).setdefault("js", {})
            cur = e.get(dk)
            if cur is None:
                e[dk] = [name, args, bool(trusted)]
            elif trusted and not cur[2]:
                cur[2] = True
        for h in neg:
            self._put(h, "unjs", dk, [name, args])
        self._ok(list_id, "js")

    # -- output --
    def cos_dict(self):
        return {"lowly": {k: list(v) for k, v in self.lowly.items()}, "high": list(self.high),
                "unhide": list(self.gunhide)}

    def site_rows(self):
        for key, fields in self.site.items():
            d = {f: list(v.values()) for f, v in fields.items()}
            yield key, json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        if self.re_keys:
            yield "/", json.dumps({"re": self.re_keys}, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------------------------------------
def _read(path, dropped):
    try:
        if os.path.getsize(path) > MAX_FILE:
            dropped["file_too_big"] = dropped.get("file_too_big", 0) + 1
            return None
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        dropped["file_missing"] = dropped.get("file_missing", 0) + 1
        return None


def _include_loader(entry, lists_dir, stats):
    incs = {}
    for p in entry.get("includes") or []:
        b = os.path.basename(p)
        incs[b] = p
        if "__" in b:
            incs.setdefault(b.split("__", 1)[1], p)
    lid = entry.get("id", "")

    def load(name):
        if not _safe_include_name(name):
            return None
        p = incs.get(name)
        if p is None and lists_dir:
            cand = os.path.join(lists_dir, "%s__%s" % (lid, name))
            if os.path.isfile(cand):
                p = cand
        if p is None:
            return None
        return _read(p, stats)
    return load


def compile_lists(cfg, out_dir, lists_dir=None, netfilter=None):
    """Compile config dict into out_dir (created). Returns the info dict."""
    t0 = time.perf_counter()
    os.makedirs(out_dir, exist_ok=True)
    b = Builder()
    pstats = {}
    for entry in cfg.get("lists") or []:
        lid = str(entry.get("id") or "?")
        path = entry.get("path") or ""
        if lists_dir and not os.path.isabs(path):
            path = os.path.join(lists_dir, path)
        text = _read(path, b.dropped)
        if text is None:
            b.counts.setdefault(lid, 0)
            continue
        trusted = bool(entry.get("trusted"))
        b.counts.setdefault(lid, 0)
        for line in preprocess(text, _include_loader(entry, lists_dir, b.dropped), pstats):
            try:
                b.add(line, lid, trusted)
            except Exception:
                b.errors += 1
    user = cfg.get("user") or ""
    if user.strip():
        b.counts.setdefault("user", 0)
        for line in preprocess(user, None, pstats):
            try:
                b.add(line, "user", False)
            except Exception:
                b.errors += 1
    t_parse = time.perf_counter()

    if netfilter is None:
        from . import netfilter as netfilter          # ENGINE-B
    net = netfilter.compile_network(b.net)
    with open(os.path.join(out_dir, "net.bin"), "wb") as f:
        marshal.dump(net, f)
    t_net = time.perf_counter()

    with open(os.path.join(out_dir, "cos.bin"), "wb") as f:
        marshal.dump(b.cos_dict(), f)

    dbp = os.path.join(out_dir, "site.db")
    if os.path.exists(dbp):
        os.remove(dbp)
    con = sqlite3.connect(dbp)
    try:
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("CREATE TABLE site(key TEXT PRIMARY KEY, data TEXT)")
        con.executemany("INSERT INTO site VALUES (?, ?)", b.site_rows())
        con.commit()
    finally:
        con.close()

    pp = cfg.get("psl")
    if pp:
        txt = _read(pp, b.dropped)
        if txt:
            with open(os.path.join(out_dir, "psl.bin"), "wb") as f:
                marshal.dump(_psl.parse(txt), f)

    ms = int((time.perf_counter() - t0) * 1000)
    info = {"format": FORMAT, "counts": b.counts, "total": sum(b.counts.values()), "errors": b.errors,
            "ms": ms, "detail": b.detail, "dropped": b.dropped, "preprocessor": pstats,
            "sizes": {"site_keys": len(b.site), "generic_lowly": sum(len(v) for v in b.lowly.values()),
                      "generic_high": len(b.high), "generic_unhide": len(b.gunhide), "net_items": len(b.net)},
            "timing_ms": {"parse": int((t_parse - t0) * 1000), "net": int((t_net - t_parse) * 1000)},
            "built": int(time.time())}
    with open(os.path.join(out_dir, "info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        _err("usage: compiler <lists_dir> <out_dir> <config.json>")
        sys.exit(2)
    lists_dir, out_dir, cfg_path = argv
    out_dir = os.path.abspath(out_dir)
    tmp = out_dir.rstrip("\\/") + ".tmp"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        compile_lists(cfg, tmp, lists_dir)
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.replace(tmp, out_dir)
    except Exception:
        tb = traceback.format_exc()
        _err(tb)
        try:
            with open(out_dir.rstrip("\\/") + ".err", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(1)
    sys.exit(0)


def _err(msg):
    try:
        if sys.stderr is not None:
            sys.stderr.write(msg + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
