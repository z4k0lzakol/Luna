# Luna ad blocker: uBO-style static network filters (clean-room).
# compile_network() runs in the compiler subprocess; NetEngine runs on the GUI thread.
#
# Compiled form (marshal-able dict, see compile_network):
#   "hosts": bytes of sorted array('Q') = blake2b-64 of every plain "||host^" block filter
#   "sets":  {name: (host_idx, token_idx, domain_idx, untok_idx)} for
#            B (block), E (exceptions), R (redirect directives), RE (redirect exceptions),
#            P (removeparam), PE (removeparam exceptions), F (page-flag exceptions)
#   filter tuple: (pat, fl, tmask, dpos, dneg, tpos, tneg, meth, extra, text)
#     pat = None (match all / implied by host index) | str (lower-case substring)
#           | (anchors, segs) wildcard pattern | (-1, regex_src, match_case)
#     segs = tuple of str (plain) or 1-tuple (str_with_caret,)
import re
import sys
import warnings
from array import array
from bisect import bisect_left
from hashlib import blake2b
from urllib.parse import quote

FORMAT = 1


class RT:
    DOCUMENT = 1
    SUBDOCUMENT = 2
    STYLESHEET = 3
    SCRIPT = 4
    IMAGE = 5
    FONT = 6
    OBJECT = 7
    MEDIA = 8
    XHR = 9
    PING = 10
    WEBSOCKET = 11
    OTHER = 12
    POPUP = 13


DOCUMENT, SUBDOCUMENT, STYLESHEET, SCRIPT, IMAGE, FONT, OBJECT, MEDIA, XHR, PING, WEBSOCKET, OTHER, POPUP = range(1, 14)

# page_flags bits
GHIDE, SHIDE, EHIDE, DOC, JS_OFF = 1, 2, 4, 8, 16

_DOC_BIT = 1 << DOCUMENT
_POPUP_BIT = 1 << POPUP
_ALL_NET = 0
for _t in range(SUBDOCUMENT, OTHER + 1):
    _ALL_NET |= 1 << _t
_ALL = _ALL_NET | _DOC_BIT | _POPUP_BIT

_TYPES = {
    "script": SCRIPT, "image": IMAGE, "stylesheet": STYLESHEET, "css": STYLESHEET,
    "xmlhttprequest": XHR, "xhr": XHR, "subdocument": SUBDOCUMENT, "frame": SUBDOCUMENT,
    "media": MEDIA, "font": FONT, "object": OBJECT, "object-subrequest": OBJECT,
    "ping": PING, "beacon": PING, "websocket": WEBSOCKET, "other": OTHER,
    "document": DOCUMENT, "doc": DOCUMENT, "popup": POPUP,
}
# options we recognise but cannot apply in Qt (filter is dropped and counted)
_UNSUPPORTED = {
    "csp", "header", "permissions", "replace", "urlskip", "uritransform", "ipaddress", "inline-script",
    "inline-font", "cname", "rewrite", "popunder", "genericblock", "webrtc", "top", "requestheader",
    "removeheader", "stealth", "cookie", "jsinject", "urlblock", "content", "extension", "app", "network",
    "hls", "jsonprune", "referrerpolicy", "redirect-url", "xmlprune", "responseheader", "elemhide-only",
}
_METHODS = {"get": 1, "post": 2, "head": 4, "put": 8, "delete": 16, "options": 32, "patch": 64, "connect": 128}

# filter flag bits
_P1, _P3, _S1, _S3, _IMP, _DSLOW, _TSLOW = 1, 2, 4, 8, 16, 32, 64
# pattern anchors
_HOST, _LEFT, _RIGHT = 1, 2, 4

_NONSEP = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.%")
# tokens = runs of [0-9a-z]; a percent escape %XX is one separator unit (so "%2Ftwitter" -> "twitter")
_TOKRE = re.compile(r"%[0-9a-f]{2}|[0-9a-z]{2,}")
_TOKCH = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")
_HEX = frozenset("0123456789abcdef")
_REGEX_CAP = 2048
_TOKEN_CAP = 4096
_RP_CAP = 8192      # removeparam is skipped for longer URLs (bounded GUI-thread work)

# redirect resources: canonical names + aliases (spec 04)
_REDIRECT_NAMES = {
    "1x1.gif": ("1x1-transparent.gif", "1x1-transparent-gif"),
    "2x2.png": ("2x2-transparent.png", "2x2-transparent-png"),
    "3x2.png": ("3x2-transparent.png", "3x2-transparent-png"),
    "32x32.png": ("32x32-transparent.png", "32x32-transparent-png"),
    "noop.css": ("noopcss", "blank-css"),
    "noop.html": ("noopframe", "blank-html"),
    "noop.js": ("noopjs", "blank-js"),
    "noop.json": ("noopjson",),
    "noop.txt": ("nooptext", "blank-text"),
    "empty": (),
    "none": (),
    "noop-0.1s.mp3": ("noopmp3-0.1s", "blank-mp3"),
    "noop-0.5s.mp3": (),
    "noop-1s.mp4": ("noopmp4-1s", "blank-mp4"),
    "noop-vast2.xml": ("noopvast-2.0",),
    "noop-vast3.xml": ("noopvast-3.0",),
    "noop-vast4.xml": ("noopvast-4.0",),
    "noop-vmap1.xml": ("noop-vmap1.0.xml", "noopvmap-1.0"),
    "click2load.html": (),
    "googletagservices_gpt.js": ("googletagservices.com/gpt.js", "googletagservices-gpt"),
    "googlesyndication_adsbygoogle.js": ("googlesyndication.com/adsbygoogle.js", "googlesyndication-adsbygoogle"),
    "google-ima.js": ("google-ima3",),
    "google-analytics_analytics.js": ("google-analytics.com/analytics.js", "google-analytics"),
    "google-analytics_ga.js": ("google-analytics.com/ga.js", "google-analytics-ga"),
    "google-analytics_cx_api.js": ("google-analytics.com/cx/api.js",),
    "google-analytics_inpage_linkid.js": ("google-analytics.com/inpage_linkid.js",),
    "googletagmanager_gtm.js": ("googletagmanager.com/gtm.js",),
    "amazon_apstag.js": ("amazon-apstag",),
    "amazon_ads.js": ("amazon-adsystem.com/aax2/amzn_ads.js",),
    "ampproject_v0.js": ("ampproject.org/v0.js",),
    "doubleclick_instream_ad_status.js": ("doubleclick.net/instream/ad_status.js",),
    "scorecardresearch_beacon.js": ("scorecardresearch.com/beacon.js", "scorecardresearch-beacon"),
    "outbrain-widget.js": ("widgets.outbrain.com/outbrain.js",),
    "hd-main.js": (),
    "fingerprint2.js": ("fingerprintjs2",),
    "fingerprint3.js": ("fingerprintjs3",),
    "nobab.js": ("bab-defuser.js", "prevent-bab"),
    "nobab2.js": ("prevent-bab2",),
    "nofab.js": ("fuckadblock.js-3.2.0", "prevent-fab-3.2.0"),
    "popads.js": ("popads.net.js", "prevent-popads-net"),
    "popads-dummy.js": ("set-popads-dummy",),
    "prebid-ads.js": ("prebid-ads",),
    "sensors-analytics.js": (),
    "nitropay_ads.js": (),
    "adthrive_abd.js": (),
    "noeval.js": (),
    "noeval-silent.js": ("silent-noeval.js", "noeval"),
    "chartbeat.js": ("static.chartbeat.com/chartbeat.js",),
    "ligatus_angular-tag.js": ("ligatus.com/*/angular-tag.js",),
    "addthis_widget.js": ("addthis.com/addthis_widget.js",),
    "monkeybroker.js": ("d3pkae9owd2lcf.cloudfront.net/mb105.js",),
    "piano-analytics.js": (),
}
REDIRECT_ALIASES = {}
for _c, _al in _REDIRECT_NAMES.items():
    REDIRECT_ALIASES[_c] = _c
    for _a in _al:
        REDIRECT_ALIASES[_a] = _c


def canonical_redirect(name, known=None):
    """Alias → canonical resource name; None if unknown."""
    n = name.strip()
    if n.startswith("abp-resource:"):
        n = n[13:]
    c = REDIRECT_ALIASES.get(n)
    if c is None and known is not None and n in known:
        c = n
    return c


def _h64(s):
    return int.from_bytes(blake2b(s.encode(), digest_size=8).digest(), "little")


def _default_registrable(host):
    """Luna's base_domain heuristic (no PSL)."""
    if not host:
        return ""
    if _is_ip(host):
        return host
    p = host.strip(".").split(".")
    if len(p) >= 3 and p[-2] in ("co", "com", "org", "net", "gov", "edu", "ac", "gob"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def _is_ip(h):
    if not h:
        return False
    if h[0] == "[" or ":" in h:
        return True
    return h[-1].isdigit() and h.replace(".", "").isdigit()


def _host_of(url):
    """lower-case host of an (encoded) URL; '' if none."""
    i = url.find("://")
    if i < 0:
        return ""
    s, n = i + 3, len(url)
    e = n
    for ch in "/?#":
        k = url.find(ch, s, e)
        if k >= 0:
            e = k
    a = url.rfind("@", s, e)
    if a >= 0:
        s = a + 1
    h = url[s:e]
    if h.startswith("["):
        k = h.find("]")
        return h[:k + 1].lower() if k > 0 else h.lower()
    k = h.find(":")
    if k >= 0:
        h = h[:k]
    return h.lower().rstrip(".")


def _host_span(u):
    """(start, end) of the host inside URL u."""
    i = u.find("://")
    if i < 0:
        return 0, 0
    s = i + 3
    e = len(u)
    for ch in "/?#":
        k = u.find(ch, s, e)
        if k >= 0:
            e = k
    a = u.rfind("@", s, e)
    if a >= 0:
        s = a + 1
    if u.startswith("[", s):
        k = u.find("]", s, e)
        return s, (k + 1 if k > 0 else e)
    k = u.find(":", s, e)
    if k >= 0:
        e = k
    return s, e


# ------------------------------------------------------------------ pattern matching (linear, no wildcard regex)
_SEGC = {}   # caret segment -> compiled fixed-shape regex (no quantifiers -> linear)
_RXC = {}    # regex filter source -> compiled | False
_SEPCLS = r"(?:[^0-9A-Za-z_.%\-]|\Z)"


def _segrx(s):
    rx = _SEGC.get(s)
    if rx is None:
        rx = _SEGC[s] = re.compile(_SEPCLS.join(re.escape(x) for x in s.split("^")), re.S)
    return rx


def _at(u, seg, p):
    """seg matches exactly at p -> end index, else -1"""
    if seg.__class__ is str:
        return p + len(seg) if u.startswith(seg, p) else -1
    m = _segrx(seg[0]).match(u, p)
    return m.end() if m else -1


def _find(u, seg, p):
    """leftmost match of seg at >= p -> end index, else -1"""
    if seg.__class__ is str:
        i = u.find(seg, p)
        return i + len(seg) if i >= 0 else -1
    s = seg[0]
    rx = _segrx(s)
    lead = 0
    while lead < len(s) and s[lead] == "^":
        lead += 1
    part = s[lead:].split("^", 1)[0]
    if part:
        # literal-driven: C-speed find, a few anchored regex checks, then regex search from there
        i = u.find(part, p + lead)
        tries = 0
        while i >= 0 and tries < 16:
            m = rx.match(u, i - lead)
            if m:
                return m.end()
            i = u.find(part, i + 1)
            tries += 1
        if i < 0:
            return -1
        p = i - lead
    m = rx.search(u, p)
    return m.end() if m else -1


def _tail(u, seg, p):
    """seg matches ending exactly at len(u), starting >= p"""
    L = len(u)
    if seg.__class__ is str:
        return u.endswith(seg) and L - len(seg) >= p
    s = seg[0]
    c = s.count("^")
    n = len(s) - c                # literal chars; each ^ takes 1 char, trailing ones may take 0 (end)
    z = len(s) - len(s.rstrip("^"))
    rx = _segrx(s)
    for st in range(L - n - c, L - n - c + z + 1):
        if st >= p:
            m = rx.match(u, st)
            if m and m.end() == L:
                return True
    return False


def _rest(u, segs, i, cur, right):
    n = len(segs)
    last = n - 1
    while i < n:
        seg = segs[i]
        if i == last and right:
            return _tail(u, seg, cur)
        cur = _find(u, seg, cur)
        if cur < 0:
            return False
        i += 1
    return (cur == len(u)) if right else True


def _re_get(src, mc):
    k = (src, mc)
    rx = _RXC.get(k)
    if rx is None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rx = re.compile(_js2py(src), 0 if mc else re.I)
        except Exception:
            rx = False
        _RXC[k] = rx
    return rx


_WILDQ = re.compile(r"(?:\.|\\[DSWdsw]|\])[*+]")
_CAPC = {}


def _re_cap(src):
    """input cap for a regex filter: 2 KB, 512 B when >=2 unbounded wildcards (polynomial backtracking)"""
    c = _CAPC.get(src)
    if c is None:
        c = _CAPC[src] = 512 if len(_WILDQ.findall(src)) >= 2 else _REGEX_CAP
    return c


def _pm(p, u, U, hs, he):
    a = p[0]
    if a < 0:
        rx = _re_get(p[1], p[2])
        if rx is False:
            return False
        cap = _re_cap(p[1])
        return rx.search(U if len(U) <= cap else U[:cap]) is not None
    segs = p[1]
    right = a & _RIGHT
    if a & _HOST:
        s0 = segs[0]
        pos = hs
        while True:
            e = _at(u, s0, pos)
            if e >= 0 and _rest(u, segs, 1, e, right):
                return True
            pos = u.find(".", pos, he)
            if pos < 0:
                return False
            pos += 1
    if a & _LEFT:
        e = _at(u, segs[0], 0)
        return e >= 0 and _rest(u, segs, 1, e, right)
    return _rest(u, segs, 0, 0, right)


def _js2py(src):
    s = re.sub(r"\(\?<([A-Za-z_])", r"(?P<\1", src)
    return s.replace("[^]", r"[\s\S]")


# ------------------------------------------------------------------ parsing
class _Skip(Exception):
    def __init__(self, kind, what=""):
        self.kind, self.what = kind, what


_BARE_HOST = re.compile(r"[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?)+")
_PURE_HOST = re.compile(r"([a-z0-9_-]+(?:\.[a-z0-9_-]+)*)\^")
_HOST_PREFIX = re.compile(r"([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)[/^:]")
_OPTNAME = re.compile(r"~?[a-z0-9_-]+(?:=|$)", re.I)
_REDOS = re.compile(r"\((?:[^()\\]|\\.)*(?<!\\)[+*](?:[^()\\]|\\.)*\)(?:[+*]|\{\d*,)")
_FAST_HOST = re.compile(r"\|\|([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)\^")

_BAD_TOKENS = frozenset("""http https www com net org js html htm php asp aspx jpg jpeg png gif webp svg ico css json
xml txt static cdn img images image assets api min v1 v2 v3 pl de uk co io fr it ru eu us info media content files
file www2 en js2 ad ads""".split())

_intern = {}


def _I(s):
    return _intern.setdefault(s, s)


def _split_opts(body):
    """-> (pattern, [option strings]) ; options anchor = rightmost '$' whose tail parses as options"""
    k = body.rfind("$")
    while k >= 0:
        tail = body[k + 1:]
        if tail:
            parts = _split_commas(tail)
            if all(_OPTNAME.match(o) for o in parts):
                return body[:k], parts
        k = body.rfind("$", 0, k)
    return body, []


def _split_commas(s):
    if "\\," not in s:
        return s.split(",")
    out, cur, i, n = [], [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] == ",":
            cur.append(","); i += 2; continue
        if c == ",":
            out.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def _idna(h):
    if h.isascii():
        return h
    try:
        return h.encode("idna").decode("ascii")
    except Exception:
        out = []
        for lab in h.split("."):
            if lab.isascii():
                out.append(lab)
            else:
                try:
                    out.append("xn--" + lab.encode("punycode").decode("ascii"))
                except Exception:
                    raise _Skip("invalid", "idna")
        return ".".join(out)


def _split_domains(v):
    out, i, n = [], 0, len(v)
    while i < n:
        neg = False
        if v[i] == "~":
            neg, i = True, i + 1
        if i < n and v[i] == "/":
            j = i + 1
            while j < n:
                if v[j] == "\\":
                    j += 2; continue
                if v[j] == "/" and (j + 1 == n or v[j + 1] == "|"):
                    break
                j += 1
            out.append((neg, v[i:j + 1])); i = j + 2
        else:
            j = v.find("|", i)
            if j < 0:
                j = n
            out.append((neg, v[i:j])); i = j + 1
    return out


def _domain_sets(v, allow_neg=True, allow_entity=True):
    pos, neg, slow = set(), set(), False
    for ng, d in _split_domains(v):
        d = d.strip()
        if not d:
            continue
        if d.startswith("/") and len(d) > 2 and d.endswith("/"):
            if not _re_get(d[1:-1], False):
                continue
            slow = True
        else:
            d = _idna(d.lower().strip("."))
            if not d or d == "*":
                continue
            if d.endswith(".*") and not allow_entity:
                continue
        if ng:
            if not allow_neg:
                raise _Skip("invalid", "negated")
            neg.add(_I(d))
        else:
            pos.add(_I(d))
    if pos and neg:
        slow = True
    return (frozenset(pos) if pos else None), (frozenset(neg) if neg else None), slow


def _norm_nonascii(p):
    """non-ASCII pattern text -> punycode host part + percent-encoded rest (lower-case hex)"""
    out = []
    i = 0
    if p.startswith("||"):
        m = re.match(r"\|\|([^/^*:|?]*)", p)
        out.append("||" + _idna(m.group(1)))
        i = m.end()
    for ch in p[i:]:
        out.append(ch if ch.isascii() else quote(ch, safe="").lower())
    return "".join(out)


def _tokens_of_pattern(p, anch):
    """safe tokens of a lower-case wildcard pattern (bounded by known non-token chars)"""
    toks = []
    n = len(p)
    i = 0
    while i < n:
        c = p[i]
        if c == "%":
            i += 3 if i + 2 < n and p[i + 1] in _HEX and p[i + 2] in _HEX else 1
            continue
        if c in _TOKCH:
            j = i
            while j < n and p[j] in _TOKCH:
                j += 1
            if j - i >= 2:
                if i == 0:
                    lok = bool(anch & (_HOST | _LEFT))
                else:
                    lok = p[i - 1] != "*"
                if j == n:
                    rok = bool(anch & _RIGHT)
                else:
                    rok = p[j] != "*"
                if lok and rok:
                    toks.append(p[i:j])
            i = j
        else:
            i += 1
    return toks


_U, _B = None, True  # regex sequence markers: unknown char / boundary (anchor)


def _regex_tokens(src):
    """safe literal tokens of a regex (conservative; [] when unsure)"""
    seq = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            if i + 1 >= n:
                return []
            d = src[i + 1]
            if d.isalnum():
                i += 2
                if d == "x":
                    i += 2
                elif d == "u":
                    if i < n and src[i] == "{":
                        k = src.find("}", i); i = (k + 1) if k > 0 else n
                    else:
                        i += 4
                elif d == "c":
                    i += 1
                elif d.isdigit():
                    while i < n and src[i].isdigit():
                        i += 1
                elif d in "pPk" and i < n and src[i] in "{<":
                    k = src.find("}" if src[i] == "{" else ">", i); i = (k + 1) if k > 0 else n
                seq.append(_U)
                continue
            seq.append(d)
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and src[j] == "^":
                j += 1
            if j < n and src[j] == "]":
                j += 1
            while j < n and src[j] != "]":
                if src[j] == "\\":
                    j += 1
                j += 1
            if j >= n:
                return []
            seq.append(_U); i = j + 1
            continue
        if c == "(":
            depth, j = 1, i + 1
            while j < n and depth:
                cj = src[j]
                if cj == "\\":
                    j += 2; continue
                if cj == "[":
                    j += 1
                    if j < n and src[j] == "^":
                        j += 1
                    if j < n and src[j] == "]":
                        j += 1
                    while j < n and src[j] != "]":
                        if src[j] == "\\":
                            j += 1
                        j += 1
                elif cj == "(":
                    depth += 1
                elif cj == ")":
                    depth -= 1
                j += 1
            if depth:
                return []
            seq.append(_U); i = j
            continue
        if c == "|":
            return []
        if c == ".":
            seq.append(_U)
        elif c == "^":
            seq.append(_B if i == 0 else _U)
        elif c == "$":
            seq.append(_B if i == n - 1 else _U)
        elif c in "?*":
            if seq:
                seq[-1] = _U
            seq.append(_U)
        elif c == "+":
            seq.append(_U)
        elif c == "{":
            k = src.find("}", i)
            if k < 0:
                seq.append("{")
            else:
                q = src[i + 1:k]
                if re.fullmatch(r"\d+(,\d*)?", q):
                    if q.split(",")[0] == "0" and seq:
                        seq[-1] = _U
                    seq.append(_U)
                    i = k
                else:
                    seq.append("{")
        else:
            seq.append(c)
        i += 1
    toks = []
    m = len(seq)
    k = 0
    while k < m:
        x = seq[k]
        if isinstance(x, str) and x.lower() in _TOKCH:
            j = k
            while j < m and isinstance(seq[j], str) and seq[j].lower() in _TOKCH:
                j += 1
            left = seq[k - 1] if k > 0 else _U
            right = seq[j] if j < m else _U
            lok = left is _B or (isinstance(left, str) and left.lower() not in _TOKCH)
            rok = right is _B or (isinstance(right, str) and right.lower() not in _TOKCH)
            run = "".join(seq[k:j]).lower()
            if left == "%":
                # the URL tokenizer eats "%XX" as one unit; a preceding '%' after a quantifier is unknown
                if k >= 2 and seq[k - 2] is _U:
                    lok = False
                elif len(run) >= 2 and run[0] in _HEX and run[1] in _HEX:
                    run = run[2:]
            if lok and rok and len(run) >= 2:
                toks.append(run)
            k = j
        else:
            k += 1
    return toks


class _F:
    """compile-time filter record"""
    __slots__ = ("exc", "pat", "pkey", "purehost", "hostkey", "toks", "fl", "tmask", "dpos", "dneg", "tpos",
                 "tneg", "meth", "role", "extra", "text", "lid", "explicit_types", "has_opts")

    def key(self):
        return (self.exc, self.pkey, self.tmask, self.fl, self.dpos, self.dneg, self.tpos, self.tneg, self.meth,
                self.role, self.extra if self.role != "B" else None)

    def tup(self):
        return (self.pat, self.fl, self.tmask, self.dpos, self.dneg, self.tpos, self.tneg, self.meth,
                self.extra, self.text)


def parse_filter(text, known_redirects=None):
    """One network filter line -> list of _F (one line may yield B+R / F+E records). Raises _Skip."""
    t = text.strip()
    if not t or t[0] in "!#" or t.startswith("[") or len(t) > 8192:
        raise _Skip("comment")
    if re.search(r"#[@?$%]*#|#@?\$\??#|#%#", t):
        raise _Skip("cosmetic")
    exc = t.startswith("@@")
    body = t[2:] if exc else t
    pat, opts = _split_opts(body)

    # ---- options
    pos_t = neg_t = 0
    fl = 0
    imp = mc = bad = False
    dpos = dneg = tpos = tneg = None
    dslow = tslow = False
    meth = 0
    redirect = rrule = None
    rp = None          # removeparam value (None = absent)
    cflags = 0
    all_t = False
    party1 = party3 = False
    for o in opts:
        o = o.strip()
        if not o:
            continue
        name, eq, val = o.partition("=")
        name = name.lower().strip()
        neg = name.startswith("~")
        if neg:
            name = name[1:]
        if name in _TYPES:
            b = 1 << _TYPES[name]
            if neg:
                neg_t |= b
            else:
                pos_t |= b
        elif name == "all":
            all_t = True
        elif name in ("third-party", "3p"):
            if neg:
                party1 = True
            else:
                party3 = True
        elif name in ("first-party", "1p"):
            if neg:
                party3 = True
            else:
                party1 = True
        elif name in ("strict1p", "strict-first-party"):
            fl |= _S1
        elif name in ("strict3p", "strict-third-party"):
            fl |= _S3
        elif name == "important":
            imp = True
        elif name == "badfilter":
            bad = True
        elif name == "match-case":
            mc = True
        elif name in ("domain", "from"):
            if not val:
                raise _Skip("invalid", "domain")
            dpos, dneg, dslow = _domain_sets(val)
            if dpos is None and dneg is None:
                raise _Skip("invalid", "domain")
        elif name == "to":
            if not val:
                raise _Skip("invalid", "to")
            tpos, tneg, tslow = _domain_sets(val)
            if tpos is None and tneg is None:
                raise _Skip("invalid", "to")
        elif name == "denyallow":
            if not val:
                raise _Skip("invalid", "denyallow")
            p2, n2, _s = _domain_sets(val, allow_neg=False, allow_entity=False)
            if p2:
                tneg = (tneg or frozenset()) | p2
        elif name == "method":
            for mname in val.lower().split("|"):
                mn = mname.startswith("~")
                bit = _METHODS.get(mname.lstrip("~"))
                if bit is None:
                    raise _Skip("invalid", "method")
                if mn:
                    meth |= bit << 10
                else:
                    meth |= bit
        elif name in ("redirect", "redirect-rule"):
            if name == "redirect":
                redirect = val
            else:
                rrule = val
            if not val and not exc:
                raise _Skip("invalid", name)
        elif name == "empty":
            redirect = "empty"
        elif name == "mp4":
            redirect = "noop-1s.mp4"
            if not pos_t:
                pos_t |= 1 << MEDIA
        elif name in ("removeparam", "queryprune"):
            rp = val if eq else ""
        elif name in ("generichide", "ghide"):
            cflags |= GHIDE
        elif name in ("specifichide", "shide"):
            cflags |= SHIDE
        elif name in ("elemhide", "ehide"):
            cflags |= EHIDE
        elif name == "reason" or set(name) == {"_"}:
            pass
        elif name in _UNSUPPORTED:
            raise _Skip("unsupported", name)
        else:
            raise _Skip("unknown", name)
    meaningful = any(o.strip().lower() not in ("badfilter", "") and not o.strip().lower().startswith("reason=")
                     and set(o.strip()) != {"_"} for o in opts)

    # ---- pattern
    if not pat.isascii():
        pat = _norm_nonascii(pat)
    is_re = len(pat) > 2 and pat[0] == "/" and pat[-1] == "/"
    anch = 0
    purehost = hostkey = None
    toks = []
    if is_re:
        src = pat[1:-1]
        if _REDOS.search(src):
            raise _Skip("invalid", "regex-redos")     # nested quantifier -> exponential backtracking
        if not _re_get(src, mc):
            raise _Skip("invalid", "regex")
        cpat = (-1, src, bool(mc))
        pkey = ("re", src, bool(mc))
        toks = _regex_tokens(src)
    else:
        if mc:
            raise _Skip("unsupported", "match-case")   # uBO: match-case only for regex filters
        p = pat.lower()
        if p and p[0] not in "|*/^" and _BARE_HOST.fullmatch(p):
            p = "||" + p + "^"                         # uBO: bare hostname == ||host^
        if p.startswith("||"):
            anch |= _HOST; p = p[2:]
        elif p.startswith("|"):
            anch |= _LEFT; p = p[1:]
        if p.endswith("|"):
            anch |= _RIGHT; p = p[:-1]
        while "**" in p:
            p = p.replace("**", "*")
        if p.startswith("*"):
            anch &= ~(_HOST | _LEFT)
            p = p[1:]
        if p.endswith("*"):
            anch &= ~_RIGHT
            p = p[:-1]
        if not p and anch & _HOST:
            anch = 0
        if not p and not anch:
            cpat = None
            pkey = ("all",)
        else:
            m = _PURE_HOST.fullmatch(p) if anch == _HOST else None
            if m:
                purehost = _I(m.group(1))
                cpat = None
                pkey = ("host", purehost)
                hostkey = purehost
            elif not anch and "*" not in p and "^" not in p:
                cpat = p
                pkey = ("lit", p)
                toks = _tokens_of_pattern(p, anch)
            else:
                segs = tuple((s,) if "^" in s else s for s in p.split("*"))
                cpat = (anch, segs)
                pkey = ("pat", anch, p)
                if anch & _HOST:
                    hm = _HOST_PREFIX.match(segs[0] if segs[0].__class__ is str else segs[0][0])
                    if hm:
                        hostkey = _I(hm.group(1))
                toks = _tokens_of_pattern(p, anch)

    # ---- types / party
    explicit = bool(pos_t) or all_t
    if all_t:
        pos_t |= _ALL
    if pos_t:
        tmask = pos_t & ~neg_t
    else:
        # uBO strict blocking: a pure "||host^" without any type option also covers the document
        dflt = _ALL_NET | (_DOC_BIT if purehost and not neg_t else 0)
        tmask = dflt & ~neg_t
    if party1 and not party3:
        fl |= _P1
    elif party3 and not party1:
        fl |= _P3
    if (fl & _S1) and (fl & _S3):
        fl &= ~(_S1 | _S3)
    if dslow:
        fl |= _DSLOW
    if tslow:
        fl |= _TSLOW

    def mk(role, extra, tm, flags):
        f = _F()
        f.exc, f.pat, f.pkey, f.purehost, f.hostkey, f.toks = exc, cpat, pkey, purehost, hostkey, toks
        f.fl, f.tmask, f.dpos, f.dneg, f.tpos, f.tneg, f.meth = flags, tm, dpos, dneg, tpos, tneg, meth
        f.role, f.extra, f.text, f.lid = role, extra, t, None
        f.explicit_types, f.has_opts = explicit, meaningful
        return f

    out = []
    if not exc:
        if cflags:
            raise _Skip("invalid", "cosmetic-option-on-block")
        if denyallow_without_domain(opts, dpos):
            raise _Skip("invalid", "denyallow")
        flags = fl | (_IMP if imp else 0)
        if rp is not None:
            out.append(mk("P", _rp_spec(rp), tmask if pos_t else (tmask | _DOC_BIT), flags))
        elif rrule is not None or redirect is not None:
            nm, pr = _redir(rrule if rrule is not None else redirect, known_redirects)
            rtm = tmask & ~(_DOC_BIT | _POPUP_BIT) if not pos_t else tmask
            if not rtm:
                raise _Skip("invalid", "redirect-type")
            if redirect is not None and rrule is None:
                out.append(mk("B", None, rtm, flags))
            out.append(mk("R", (nm, pr), rtm, flags))
        else:
            if not tmask:
                raise _Skip("invalid", "types")
            out.append(mk("B", None, tmask, flags))
    else:
        if rp is not None:
            out.append(mk("PE", _rp_key(rp), tmask if pos_t else (tmask | _DOC_BIT), fl))
        elif rrule is not None or redirect is not None:
            v = rrule if rrule is not None else redirect
            nm = "" if not v else _redir(v, known_redirects)[0]
            out.append(mk("RE", nm, tmask if pos_t else _ALL_NET, fl))
        else:
            fb = cflags
            if pos_t & _DOC_BIT:
                fb |= DOC | GHIDE | SHIDE | EHIDE | JS_OFF
            if fb & EHIDE:
                fb |= JS_OFF
            if fb:
                out.append(mk("F", fb, _ALL, fl))
            if not cflags or explicit:
                if not tmask:
                    raise _Skip("invalid", "types")
                out.append(mk("E", None, tmask, fl))
    if bad:
        for f in out:
            f.role = "BAD:" + f.role
    return out


def denyallow_without_domain(opts, dpos):
    return dpos is None and any(o.strip().lower().startswith("denyallow=") for o in opts)


def _redir(v, known):
    name, _, pr = v.rpartition(":")
    if not name or not re.fullmatch(r"-?\d+", pr):
        name, pr = v, "0"
    c = canonical_redirect(name, known)
    if c is None:
        raise _Skip("unsupported", "redirect-resource")
    if known is not None and c not in known and c not in ("none", "empty"):
        raise _Skip("unsupported", "redirect-resource")
    return c, int(pr)


def _rp_key(v):
    return v.strip()


def _rp_spec(v):
    v = v.strip()
    if not v:
        return ("", 0, None)
    if v.startswith("/"):
        k = v.rfind("/")
        if k > 0:
            src, flags = v[1:k], v[k + 1:]
            if not _re_get(src, "i" not in flags):
                raise _Skip("invalid", "removeparam-regex")
            return (v, 3, (src, "i" not in flags))
    if v.startswith("~"):
        return (v, 2, v[1:])
    return (v, 1, v)


def _apply_removeparam(url, specs):
    """remove query params per specs -> new url or None if unchanged"""
    h = url.find("#")
    frag = url[h:] if h >= 0 else ""
    base = url[:h] if h >= 0 else url
    q = base.find("?")
    if q < 0:
        return None
    query = base[q + 1:]
    if not query:
        return None
    params = query.split("&")
    lit, negs, rxs = set(), [], []
    for mode, arg in specs:
        if mode == 0:
            return base[:q] + frag
        if mode == 1:
            lit.add(arg)
        elif mode == 2:
            negs.append(arg)
        else:
            rx = _re_get(arg[0], arg[1])
            if rx:
                rxs.append(rx)
    keep = []
    for prm in params:
        nm = prm.split("=", 1)[0]
        if nm in lit:
            continue
        drop = False
        for a in negs:
            if nm != a:
                drop = True
                break
        if not drop:
            for rx in rxs:
                if rx.search(prm) is not None:
                    drop = True
                    break
        if not drop:
            keep.append(prm)
    if len(keep) == len(params):
        return None
    return base[:q] + ("?" + "&".join(keep) if keep else "") + frag


# ------------------------------------------------------------------ compile
_SETS = ("B", "E", "R", "RE", "P", "PE", "F")


def compile_network(items, known_redirects=None):
    """items: iterable of (text, list_id, trusted). Returns marshal-able dict (see module doc)."""
    if known_redirects is None:
        try:
            from . import resources as _res     # SURROGATES' list of serveable names, if present
            known_redirects = set(getattr(_res, "NAMES", ())) or None
            if known_redirects is not None:
                known_redirects = {canonical_redirect(n) or n for n in known_redirects}
        except Exception:
            known_redirects = None
    _intern.clear()
    stats = {"lines": 0, "accepted": 0, "hosts": 0, "duplicates": 0, "badfiltered": 0, "badfilter_rules": 0,
             "unsupported": 0, "unknown": 0, "invalid": 0, "per_list": {}, "skipped_options": {}}
    per_list = stats["per_list"]
    skipped = stats["skipped_options"]
    recs = {}          # key -> _F (first wins)
    bads = []
    plain_hosts = {}   # host -> list_id (fast path for "||host^")
    for item in items:
        text, lid = item[0], item[1]
        stats["lines"] += 1
        t = text.strip()
        m = _FAST_HOST.fullmatch(t)
        if m:
            h = m.group(1)
            if h in plain_hosts:
                stats["duplicates"] += 1
            else:
                plain_hosts[h] = lid
                per_list[lid] = per_list.get(lid, 0) + 1
            continue
        try:
            fs = parse_filter(t, known_redirects)
        except _Skip as e:
            if e.kind in ("unsupported", "unknown", "invalid"):
                stats[e.kind] += 1
                if e.what:
                    k = e.kind + ":" + e.what
                    skipped[k] = skipped.get(k, 0) + 1
            continue
        except Exception:
            stats["invalid"] += 1
            continue
        ok = False
        for f in fs:
            f.lid = lid
            if f.role.startswith("BAD:"):
                f.role = f.role[4:]
                bads.append(f)
                continue
            if (f.role == "B" and f.purehost and not f.has_opts):
                if f.purehost in plain_hosts:
                    stats["duplicates"] += 1
                else:
                    plain_hosts[f.purehost] = lid
                    ok = True
                continue
            k = f.key()
            if k in recs:
                stats["duplicates"] += 1
                continue
            recs[k] = f
            ok = True
        if ok:
            per_list[lid] = per_list.get(lid, 0) + 1
    # ---- badfilter
    stats["badfilter_rules"] = len(bads)
    for b in bads:
        if b.role == "B" and b.purehost and not b.has_opts:
            if plain_hosts.pop(b.purehost, None) is not None:
                stats["badfiltered"] += 1
            continue
        k = b.key()
        if k in recs:
            del recs[k]
            stats["badfiltered"] += 1
            continue
        # uBO: |http://, |https://, * with plain positive domain= -> per-domain badfilter
        if b.dpos and not b.dneg and b.pkey in (("all",), ("pat", _LEFT, "http://"), ("pat", _LEFT, "https://"),
                                                    ("lit", "http://"), ("lit", "https://")):
            for k2, f in list(recs.items()):
                if f.pkey == b.pkey and f.dpos and not f.dneg and f.exc == b.exc and f.role == b.role and \
                        f.tmask == b.tmask and f.fl == b.fl and f.tpos == b.tpos and f.tneg == b.tneg and \
                        f.meth == b.meth and (f.extra == b.extra or f.role == "B"):
                    rest = f.dpos - b.dpos
                    if rest != f.dpos:
                        stats["badfiltered"] += 1
                        if rest:
                            f.dpos = frozenset(rest)
                        else:
                            del recs[k2]
    # ---- route
    groups = {s: [] for s in _SETS}
    for f in recs.values():
        groups[f.role].append(f)
    sets = {s: _build_set(groups[s]) for s in _SETS}
    hashes = sorted({_h64(h) for h in plain_hosts})
    arr = array("Q", hashes)
    stats["hosts"] = len(hashes)
    stats["accepted"] = len(recs) + len(hashes)
    stats["by_set"] = {s: len(groups[s]) for s in _SETS}
    _intern.clear()
    return {"format": FORMAT, "hosts": arr.tobytes(), "sets": sets, "stats": stats}


def _build_set(fs):
    """-> (host_idx, token_idx, domain_idx, untok_idx); buckets are tuples of filter tuples"""
    freq = {}
    for f in fs:
        if f.hostkey is None:
            for t in set(f.toks):
                freq[t] = freq.get(t, 0) + 1
    hidx, tidx, didx, uidx = {}, {}, {}, {}
    for f in fs:
        tup = f.tup()
        if f.hostkey is not None:
            hidx.setdefault(f.hostkey, []).append(tup)
            continue
        best = None
        if f.toks:
            best = min(set(f.toks), key=lambda t: (freq[t] + (100000 if t in _BAD_TOKENS else 0), -len(t), t))
        dom_ok = f.dpos is not None and not (f.fl & _DSLOW)
        narrow = bin(f.tmask).count("1") <= 3
        if best is not None and best in _BAD_TOKENS and not dom_ok and narrow:
            best = None          # e.g. "https": cheaper to scan only for its few request types
        if best is not None and (best not in _BAD_TOKENS and freq[best] <= 64 or not dom_ok):
            tidx.setdefault(_I(best), []).append(tup)
        elif dom_ok:
            for d in f.dpos:
                didx.setdefault(d, []).append(tup)
        else:
            for rt in range(1, 14):
                if f.tmask & (1 << rt):
                    uidx.setdefault(rt, []).append(tup)
    fz = lambda d: {k: tuple(v) for k, v in d.items()}
    return (fz(hidx), fz(tidx), fz(didx), fz(uidx))


# ------------------------------------------------------------------ runtime engine
class NetEngine:
    __slots__ = ("_hosts", "_nh", "_sets", "_stats", "_reg", "_hc", "_empty")

    def __init__(self):
        self._hosts = array("Q")
        self._nh = 0
        e = ({}, {}, {}, {})
        self._empty = e
        self._sets = {s: e for s in _SETS}
        self._stats = {}
        self._reg = _default_registrable
        self._hc = {}

    @classmethod
    def from_dict(cls, d):
        self = cls()
        if not d or d.get("format") != FORMAT:
            return self
        a = array("Q")
        a.frombytes(d.get("hosts") or b"")
        self._hosts, self._nh = a, len(a)
        sets = d.get("sets") or {}
        for s in _SETS:
            if s in sets:
                self._sets[s] = sets[s]
        self._stats = d.get("stats") or {}
        return self

    def set_registrable(self, fn):
        self._reg = fn or _default_registrable
        self._hc.clear()

    def stats(self):
        st = dict(self._stats)
        st["filters"] = st.get("accepted", self._nh + sum(
            len(b) for S in self._sets.values() for idx in S for b in idx.values()))
        st["hashed_hosts"] = self._nh
        return st

    # host info: (suffixes, ctx_keys(ordered, +entities), registrable, hashed_suffix|None)
    def _hinfo(self, h):
        r = self._hc.get(h)
        if r is not None:
            return r
        if len(self._hc) > 4096:
            self._hc.clear()
        try:
            reg = self._reg(h) or h
        except Exception:
            reg = _default_registrable(h)
        if not h:
            sfx, ctx = ("",), ("",)
        elif _is_ip(h):
            sfx = ctx = (h,)
        else:
            sl = []
            s = h
            while True:
                sl.append(s)
                k = s.find(".")
                if k < 0:
                    break
                s = s[k + 1:]
            sfx = tuple(sl)
            k = reg.find(".")
            if k > 0:
                ps_len = len(reg) - k - 1
                cl = []
                for s in sl:
                    cl.append(s)
                    if len(s) >= len(reg) and s.endswith(reg):
                        cl.append(s[:-ps_len] + "*")
                ctx = tuple(cl)
            else:
                ctx = sfx
        hit = None
        if self._nh:
            a, n = self._hosts, self._nh
            for s in sfx:
                x = _h64(s)
                i = bisect_left(a, x)
                if i < n and a[i] == x:
                    hit = "||" + s + "^"
                    break
        r = (sfx, ctx, reg, hit)
        self._hc[h] = r
        return r

    def _scan(self, S, q, mode, tb=None):
        """mode 0: first match, 1: first important match, 2: all matches"""
        u, U, hs, he, hi, fi, third, tbit, rt, mbit, toks, same = q
        if tb is not None:
            tbit = tb
        hidx, tidx, didx, uidx = S
        bl = []
        if hidx:
            for s in hi[0]:
                b = hidx.get(s)
                if b is not None:
                    bl.append(b)
        if tidx:
            for t in toks:
                b = tidx.get(t)
                if b is not None:
                    bl.append(b)
        if didx:
            for k in fi[1]:
                b = didx.get(k)
                if b is not None:
                    bl.append(b)
        b = uidx.get(rt)
        if b is not None:
            bl.append(b)
        out = [] if mode == 2 else None
        fctx = fi[1]
        for b in bl:
            for f in b:
                if not f[2] & tbit:
                    continue
                fl = f[1]
                if fl:
                    if mode == 1 and not fl & _IMP:
                        continue
                    if fl & 15:
                        if fl & _P1 and third:
                            continue
                        if fl & _P3 and not third:
                            continue
                        if fl & _S1 and not same:
                            continue
                        if fl & _S3 and same:
                            continue
                    if fl & _DSLOW:
                        if not self._dslow(f[3], f[4], fctx):
                            continue
                    else:
                        d = f[3]
                        if d is not None and d.isdisjoint(fctx):
                            continue
                        d = f[4]
                        if d is not None and not d.isdisjoint(fctx):
                            continue
                    if fl & _TSLOW:
                        if not self._dslow(f[5], f[6], hi[1]):
                            continue
                    else:
                        d = f[5]
                        if d is not None and d.isdisjoint(hi[1]):
                            continue
                        d = f[6]
                        if d is not None and not d.isdisjoint(hi[1]):
                            continue
                else:
                    if mode == 1:
                        continue
                    d = f[3]
                    if d is not None and d.isdisjoint(fctx):
                        continue
                    d = f[4]
                    if d is not None and not d.isdisjoint(fctx):
                        continue
                    d = f[5]
                    if d is not None and d.isdisjoint(hi[1]):
                        continue
                    d = f[6]
                    if d is not None and not d.isdisjoint(hi[1]):
                        continue
                m = f[7]
                if m:
                    if m & 1023 and not m & mbit:
                        continue
                    if (m >> 10) & mbit:
                        continue
                p = f[0]
                if p is not None:
                    if p.__class__ is str:
                        if p not in u:
                            continue
                    elif not _pm(p, u, U, hs, he):
                        continue
                if mode == 2:
                    out.append(f)
                else:
                    return f
        return out

    def _dslow(self, pos, neg, ctx):
        """mixed / regex domain lists: most specific key wins"""
        for k in ctx:
            if neg is not None and k in neg:
                return False
            if pos is not None and k in pos:
                return True
        h = ctx[0] if ctx else ""
        if neg is not None:
            for e in neg:
                if e[:1] == "/":
                    rx = _re_get(e[1:-1], False)
                    if rx and rx.search(h):
                        return False
        if pos is not None:
            for e in pos:
                if e[:1] == "/":
                    rx = _re_get(e[1:-1], False)
                    if rx and rx.search(h):
                        return True
            return False
        return True

    def _query(self, url, host, fp_host, rtype, method):
        u = url.lower()
        hs, he = _host_span(u)
        hi = self._hinfo(host)
        fi = hi if fp_host == host else self._hinfo(fp_host)
        third = hi[2] != fi[2]
        mbit = _METHODS.get(method.lower(), 256) if method else 1
        # token index lookup only sees the first 4 KB (bounds work on huge URLs; matching still sees all)
        toks = set(_TOKRE.findall(u if len(u) <= _TOKEN_CAP else u[:_TOKEN_CAP]))
        return (u, url, hs, he, hi, fi, third, 1 << rtype, rtype, mbit, toks, hi is fi)

    def match(self, url, host, fp_host, rtype, method="GET", fp_url=""):
        """None (allow) | ("block", text) | ("redirect", resource, text) | ("removeparam", new_url, text)"""
        if not url:
            return None
        if not host:
            host = _host_of(url)
        if not fp_host:
            fp_host = _host_of(fp_url) if fp_url else host
        if method.__class__ is not str:
            method = bytes(method).decode("latin-1")
        q = self._query(url, host, fp_host, rtype, method)
        sets = self._sets
        blk = None
        if rtype != POPUP:
            blk = q[4][3]
        if blk is None:
            blk = self._scan(sets["B"], q, 0)
        if blk is not None:
            if blk.__class__ is str or not blk[1] & _IMP:
                if self._scan(sets["E"], q, 0) is not None:
                    imp = self._scan(sets["B"], q, 1)
                    if imp is None:
                        return self._removeparam(q) if rtype <= SUBDOCUMENT else None
                    blk = imp
            text = blk if blk.__class__ is str else blk[9]
            if rtype == DOCUMENT or rtype == POPUP:
                return ("block", text)
            r = self._redirect(q)
            if r is not None:
                return ("redirect", r[0], r[1])
            return ("block", text)
        if rtype <= SUBDOCUMENT:
            return self._removeparam(q)
        return None

    def _redirect(self, q):
        cands = self._scan(self._sets["R"], q, 2)
        if not cands:
            return None
        exc = None
        best = None
        for f in cands:
            nm, pr = f[8]
            imp = f[1] & _IMP
            if not imp:
                if exc is None:
                    exc = {e[8] for e in self._scan(self._sets["RE"], q, 2)}
                if "" in exc or nm in exc:
                    continue
            k = (1 if imp else 0, pr)
            if best is None or k > best[0]:
                best = (k, nm, f[9])
        if best is None or best[1] == "none":
            return None
        return best[1], best[2]

    def _removeparam(self, q):
        url = q[1]
        if "?" not in url or len(url) > _RP_CAP:
            return None
        fs = self._scan(self._sets["P"], q, 2)
        if not fs:
            return None
        exc = {e[8] for e in self._scan(self._sets["PE"], q, 2)}
        if "" in exc:
            return None
        specs, text, seen = [], None, set()
        for f in fs:
            key, mode, arg = f[8]
            if key in exc or key in seen:
                continue
            seen.add(key)
            specs.append((mode, arg))
            if text is None:
                text = f[9]
        if not specs:
            return None
        nu = _apply_removeparam(url, specs)
        return ("removeparam", nu, text) if nu and nu != url else None

    def page_flags(self, doc_url, host):
        """GHIDE=1 SHIDE=2 EHIDE=4 DOC=8 JS_OFF=16 from @@ exception filters matching the document"""
        S = self._sets["F"]
        if S is self._empty or not doc_url:
            return 0
        host = host or _host_of(doc_url)
        q = self._query(doc_url, host, host, DOCUMENT, "GET")
        bits = 0
        for f in self._scan(S, q, 2, tb=-1):
            bits |= f[8]
        return bits

    def popup(self, url, host, opener_host):
        """filter text if a $popup filter blocks opening url from opener_host"""
        if not url:
            return None
        host = host or _host_of(url)
        q = self._query(url, host, opener_host or host, POPUP, "GET")
        blk = self._scan(self._sets["B"], q, 0)
        if blk is None:
            return None
        if not blk[1] & _IMP and self._scan(self._sets["E"], q, 0) is not None:
            blk = self._scan(self._sets["B"], q, 1)
            if blk is None:
                return None
        return blk[9]


__all__ = ["RT", "compile_network", "NetEngine", "parse_filter", "GHIDE", "SHIDE", "EHIDE", "DOC", "JS_OFF",
           "canonical_redirect", "REDIRECT_ALIASES"]
