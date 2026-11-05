# Tests + benchmark for adblock/netfilter.py.  Run: python -I tests/adblock/test_netfilter.py [--no-bench]
# The benchmark uses the downloaded lists from the research scratch dir (skipped when absent) and
# critic/c6_corpus.json (3,227 real requests).
import gc
import json
import marshal
import os
import re
import statistics
import sys
import time
import tracemalloc

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from adblock import netfilter as nf  # noqa: E402
from adblock.netfilter import RT, NetEngine, compile_network  # noqa: E402

SCR = os.environ.get("LUNA_ADBLOCK_SCRATCH", r"C:\Users\User\AppData\Local\Temp\claude\C--Users-User-Documents-GitHub-Luna"
                                              r"\e1f75005-4bf9-4754-b7a0-43b7e1fc2d57\scratchpad\adblock")

FAILS = []
COUNT = [0]


def check(cond, msg):
    COUNT[0] += 1
    if not cond:
        FAILS.append(msg)
        print("FAIL:", msg)


def eng(text, **kw):
    d = compile_network([(l, "t", True) for l in text.strip().splitlines()], **kw)
    return NetEngine.from_dict(marshal.loads(marshal.dumps(d))), d


def M(e, url, rt=RT.SCRIPT, fp="www.site.com", method="GET"):
    host = nf._host_of(url)
    return e.match(url, host, fp, rt, method)


def test_basic():
    e, d = eng("""
||ads.example.com^
||track.net^$third-party
@@||track.net/ok.js
||imp.org^$important
@@||imp.org^
/banner/*/img^
|https://left.com/a|
-adbox-
||nosep.com
""")
    check(M(e, "https://x.ads.example.com/a.js") == ("block", "||ads.example.com^"), "hashed host subdomain")
    check(M(e, "https://ads.example.com/") == ("block", "||ads.example.com^"), "hashed host itself")
    check(M(e, "https://example.com/a.js") is None, "parent not blocked")
    check(M(e, "https://ads.example.com.evil.net/a.js") is None, "||host^ not inside other host")
    check(M(e, "https://ads.example.com/", RT.DOCUMENT, "ads.example.com") == ("block", "||ads.example.com^"),
          "strict blocking document")
    check(e.popup("https://ads.example.com/", "ads.example.com", "www.site.com") is None, "plain host not popup")
    check(M(e, "https://track.net/x.js") == ("block", "||track.net^$third-party"), "3p blocked")
    check(M(e, "https://track.net/x.js", fp="www.track.net") is None, "1p not blocked by $3p")
    check(M(e, "https://track.net/ok.js") is None, "exception")
    check(M(e, "https://imp.org/x.gif", RT.IMAGE) == ("block", "||imp.org^$important"), "important beats @@")
    check(M(e, "https://cdn.com/banner/300/img?x") is not None, "wildcard + caret (?)")
    check(M(e, "https://cdn.com/banner/300/img") is not None, "caret matches end")
    check(M(e, "https://cdn.com/banner/300/img.png") is None, "caret not '.'")
    check(M(e, "https://cdn.com/banner/300/imgx") is None, "caret not letter")
    check(M(e, "https://left.com/a") is not None, "left+right anchor")
    check(M(e, "https://left.com/ab") is None, "right anchor")
    check(M(e, "http://left.com/a") is None, "left anchor scheme")
    check(M(e, "https://q.com/x-adbox-1.js") is not None, "plain substring")
    check(M(e, "https://nosep.community/x.js") is not None, "||host without ^ is prefix")
    check(M(e, "https://www.nosep.com/x.js") is not None, "||host at label")
    check(M(e, "https://anosep.com/x.js") is None, "||host needs label boundary")
    st = e.stats()
    check(st["filters"] == 9 and st["hashed_hosts"] == 1, "stats %r" % (st,))


def test_types_party():
    e, _ = eng("""
||t.com^$script
||t2.com^$~script
||t3.com^$1p
||t4.com^$strict3p
||t5.com^$strict1p
||t6.com^$all
||t7.com^$doc
||t8.com^$xhr,image
""")
    check(M(e, "https://t.com/a", RT.SCRIPT) and not M(e, "https://t.com/a", RT.IMAGE), "type script")
    check(not M(e, "https://t2.com/a", RT.SCRIPT) and M(e, "https://t2.com/a", RT.IMAGE), "negated type")
    check(not M(e, "https://t2.com/", RT.DOCUMENT, "t2.com"), "options-host not strict-doc when typed")
    check(M(e, "https://t3.com/a", fp="www.t3.com") and not M(e, "https://t3.com/a"), "1p")
    check(M(e, "https://a.t4.com/a", fp="b.t4.com") and not M(e, "https://a.t4.com/a", fp="a.t4.com"), "strict3p")
    check(M(e, "https://a.t5.com/a", fp="a.t5.com") and not M(e, "https://a.t5.com/a", fp="b.t5.com"), "strict1p")
    check(M(e, "https://t6.com/", RT.DOCUMENT, "t6.com") and e.popup("https://t6.com/", "t6.com", "x.com"), "$all")
    check(M(e, "https://t7.com/", RT.DOCUMENT, "t7.com") and not M(e, "https://t7.com/a.js"), "$doc")
    check(M(e, "https://t8.com/", RT.XHR) and M(e, "https://t8.com/", RT.IMAGE) and not M(e, "https://t8.com/"), "multi")


def test_domains():
    e, _ = eng("""
/adx.js$domain=a.com|~b.a.com
/ent.js$domain=google.*
/neg.js$domain=~safe.com
*$script,domain=wp.pl
*$image,to=cdn.bad.com|~ok.cdn.bad.com
*$script,3p,denyallow=good.com|fine.net,domain=strict.org
/rx.js$domain=/^img[a-z]{3}\\.buzz$/
/mixed.js$domain=~x.com|sub.x.com
||xn--d1acufc.xn--p1ai^$script
||ż.pl^$image
/idn.js$domain=żółć.pl
""")
    check(M(e, "https://c.com/adx.js", fp="www.a.com"), "domain pos")
    check(not M(e, "https://c.com/adx.js", fp="x.b.a.com"), "domain neg more specific")
    check(not M(e, "https://c.com/adx.js", fp="c.com"), "domain other")
    check(M(e, "https://c.com/ent.js", fp="www.google.co.uk"), "entity co.uk")
    check(M(e, "https://c.com/ent.js", fp="google.de"), "entity de")
    check(not M(e, "https://c.com/ent.js", fp="notgoogle.de"), "entity strict")
    check(M(e, "https://c.com/neg.js") and not M(e, "https://c.com/neg.js", fp="www.safe.com"), "neg only")
    check(M(e, "https://any.com/x.js", fp="www.wp.pl") and not M(e, "https://any.com/x.js"), "*$domain")
    check(not M(e, "https://any.com/x.png", RT.IMAGE, fp="www.wp.pl"), "*$domain type")
    check(M(e, "https://x.cdn.bad.com/i.png", RT.IMAGE), "to=")
    check(not M(e, "https://ok.cdn.bad.com/i.png", RT.IMAGE), "to=~ more specific")
    check(M(e, "https://evil.com/a.js", fp="strict.org"), "denyallow blocks others")
    check(not M(e, "https://cdn.good.com/a.js", fp="strict.org"), "denyallow allows listed")
    check(M(e, "https://c.com/rx.js", fp="imgabc.buzz") and not M(e, "https://c.com/rx.js", fp="imgab.buzz"),
          "regex domain")
    check(M(e, "https://c.com/mixed.js", fp="sub.x.com") and not M(e, "https://c.com/mixed.js", fp="x.com"),
          "mixed domain specificity")
    check(M(e, "https://xn--d1acufc.xn--p1ai/a.js"), "punycode host")
    check(M(e, "https://www.xn--hha.pl/a.png", RT.IMAGE), "idn pattern")
    check(M(e, "https://c.com/idn.js", fp="xn--kda4b0koi.pl"), "idn domain=")


def test_method_regex_case():
    e, _ = eng("""
||m.com^$method=post
||m2.com^$method=~get
/\\/ad[0-9]+\\.js$/
/\\/Track\\.gif/$match-case,image
/CaseLit/$match-case
||long.com^$removeparam=/^foo\\$/
""")
    check(M(e, "https://m.com/a", method="POST") and not M(e, "https://m.com/a"), "method")
    check(M(e, "https://m2.com/a", method="PUT") and not M(e, "https://m2.com/a"), "method negated")
    check(M(e, "https://x.com/ad123.js") and not M(e, "https://x.com/ad123.js?x"), "regex $")
    check(M(e, "https://x.com/Track.gif", RT.IMAGE) and not M(e, "https://x.com/track.gif", RT.IMAGE), "match-case")
    check(M(e, "https://x.com/AD9.JS"), "regex case-insensitive")
    _, d = eng("/caselit$match-case\n||x.com^$csp=script-src 'none'\n||y.com^$header=via:1\n"
               "||z.com^$redirect=nonexistent.js\n||q.com^$foo")
    st = d["stats"]
    check(st["accepted"] == 0 and st["unsupported"] == 4 and st["unknown"] == 1, "unsupported counted %r" % st)


def test_badfilter_dedupe():
    e, d = eng("""
||bad.com^
||bad.com^$badfilter
||ok.com^
||ok.com^
*$image,domain=a.com|b.com
*$image,domain=a.com,badfilter
||x.com/ads/*$script,3p
||x.com/ads/*$third-party,script,badfilter
/keep/$script
""")
    check(M(e, "https://bad.com/a.js") is None, "badfilter host")
    check(M(e, "https://ok.com/a.js"), "dup kept")
    check(d["stats"]["duplicates"] == 1, "dup counted")
    check(not M(e, "https://i.com/p.png", RT.IMAGE, "a.com") and M(e, "https://i.com/p.png", RT.IMAGE, "b.com"),
          "badfilter per-domain")
    check(M(e, "https://x.com/ads/a.js", fp="y.com") is None, "badfilter option order")


def test_redirect():
    e, _ = eng("""
||r.com/ads.js$script,redirect=noopjs
||r.com/ads.js$script,redirect-rule=noop.txt:10
||r2.com^$script,redirect-rule=noop.js
||r3.com^$script,redirect=noop.js
@@||r3.com/x.js$redirect-rule
||r4.com^$image,redirect=1x1-transparent.gif
@@||r4.com/n.gif$redirect=1x1.gif
||r5.com^
*$script,redirect-rule=noop.js,domain=wp.pl
||r6.com^$xhr,redirect=noop.txt
||r6.com^$xhr,redirect=none:5
||r7.com^$media,mp4
||r8.com^$script,empty
||r9.com^$important,script,redirect=googletagservices.com/gpt.js:-5
||r9.com^$script,redirect=noop.js:100
@@||r9.com^
""")
    check(M(e, "https://r.com/ads.js") == ("redirect", "noop.txt", "||r.com/ads.js$script,redirect-rule=noop.txt:10"),
          "priority")
    check(M(e, "https://r2.com/a.js") is None, "redirect-rule alone does not block")
    check(M(e, "https://r3.com/a.js") == ("redirect", "noop.js", "||r3.com^$script,redirect=noop.js"), "redirect=")
    check(M(e, "https://r3.com/x.js") == ("block", "||r3.com^$script,redirect=noop.js"), "@@ redirect-rule all")
    check(M(e, "https://r4.com/a.gif", RT.IMAGE)[:2] == ("redirect", "1x1.gif"), "alias")
    check(M(e, "https://r4.com/n.gif", RT.IMAGE)[0] == "block", "@@ redirect=name")
    check(M(e, "https://r5.com/a.js", fp="www.wp.pl")[:2] == ("redirect", "noop.js"), "redirect-rule on hashed block")
    check(M(e, "https://r5.com/a.png", RT.IMAGE, fp="www.wp.pl")[0] == "block", "redirect-rule type")
    check(M(e, "https://r6.com/a", RT.XHR)[0] == "block", "none wins")
    check(M(e, "https://r7.com/v.mp4", RT.MEDIA)[:2] == ("redirect", "noop-1s.mp4"), "mp4")
    check(M(e, "https://r8.com/v.js")[:2] == ("redirect", "empty"), "empty")
    check(M(e, "https://r9.com/v.js")[:2] == ("redirect", "googletagservices_gpt.js"), "important redirect")
    check(M(e, "https://r5.com/", RT.DOCUMENT, "r5.com")[0] == "block", "doc never redirected")


def test_removeparam_flags_popup():
    e, _ = eng("""
*$removeparam=utm_source
||rp.com^$removeparam=/^fbclid=/
||rp2.com^$removeparam=~keep
||rp3.com^$removeparam
@@||rp3.com/ok$removeparam
@@||nort.com^$removeparam=utm_source
@@||g.com^$ghide
@@||s.com^$specifichide
@@||el.com^$elemhide
@@||d.com^$document
@@*$ghide,domain=wp.pl|o2.pl
||pop.com^$popup
@@||pop.com/ok$popup
||pop2.com^$popup,important
@@||pop2.com^$popup
||blocked.com^$doc
@@||blocked.com/fine$document
@@||blocked.com/other
""")
    u = "https://a.com/p?utm_source=x&id=1#f"
    check(M(e, u, RT.DOCUMENT, "a.com") == ("removeparam", "https://a.com/p?id=1#f", "*$removeparam=utm_source"), "rp")
    check(M(e, u, RT.SUBDOCUMENT, "b.com")[0] == "removeparam", "rp subdoc")
    check(M(e, u, RT.SCRIPT) is None, "rp only doc/subdoc")
    check(M(e, "https://rp.com/?fbclid=1&utm_source=2", RT.DOCUMENT, "rp.com")[1] == "https://rp.com/", "rp regex")
    check(M(e, "https://rp2.com/?a=1&keep=2&b", RT.DOCUMENT, "rp2.com")[1] == "https://rp2.com/?keep=2", "rp ~")
    check(M(e, "https://rp3.com/?a=1&b=2", RT.DOCUMENT, "rp3.com")[1] == "https://rp3.com/", "rp all")
    check(M(e, "https://rp3.com/ok?a=1", RT.DOCUMENT, "rp3.com") is None, "rp @@ all")
    check(M(e, "https://nort.com/?utm_source=1", RT.DOCUMENT, "nort.com") is None, "rp @@ value")
    check(M(e, "https://a.com/p?id=1", RT.DOCUMENT, "a.com") is None, "rp unchanged -> None")
    check(e.page_flags("https://www.g.com/x", "www.g.com") == nf.GHIDE, "ghide")
    check(e.page_flags("https://s.com/", "s.com") == nf.SHIDE, "shide")
    check(e.page_flags("https://el.com/", "el.com") == nf.EHIDE | nf.JS_OFF, "ehide")
    check(e.page_flags("https://d.com/", "d.com") & nf.DOC, "document")
    check(e.page_flags("https://www.o2.pl/", "www.o2.pl") == nf.GHIDE, "ghide domain=")
    check(e.page_flags("https://other.pl/", "other.pl") == 0, "no flags")
    check(M(e, "https://g.com/x.js") is None, "ghide is not a network exception")
    check(e.popup("https://pop.com/x", "pop.com", "site.com") == "||pop.com^$popup", "popup")
    check(e.popup("https://pop.com/ok", "pop.com", "site.com") is None, "popup @@")
    check(M(e, "https://pop.com/x", RT.SCRIPT) is None, "popup filter not network")
    check(e.popup("https://pop2.com/", "pop2.com", "site.com") == "||pop2.com^$popup,important", "popup important")
    check(M(e, "https://blocked.com/", RT.DOCUMENT, "blocked.com")[0] == "block", "$doc block")
    check(M(e, "https://blocked.com/fine", RT.DOCUMENT, "blocked.com") is None, "$doc + @@$document")
    check(M(e, "https://blocked.com/other", RT.DOCUMENT, "blocked.com") is not None, "untyped @@ path not doc")


def test_parsing_edge():
    e, d = eng("""
example-ads.com
0.0.0.0 ignored-should-not-crash
/ad-$removeparam=/^foo=bar\\d$/,_
||opt.com^$reason=test,_,script
/path$script,domain=x.com\t
||ws.com^$websocket
||ping.com^$ping
||ping2.com^$beacon
!comment
[Adblock Plus 2.0]
example.com##.ad
@@||cos.com^$ghide,script
""")
    check(M(e, "https://www.example-ads.com/x") is not None, "bare hostname == ||host^")
    check(M(e, "https://opt.com/a.js") is not None, "reason/_ ignored")
    check(M(e, "https://h.com/path", fp="x.com") is not None, "trailing whitespace in options")
    check(M(e, "wss://ws.com/s", RT.WEBSOCKET) is not None, "websocket")
    check(M(e, "https://ping.com/", RT.PING) and M(e, "https://ping2.com/", RT.PING), "ping/beacon")
    check(M(e, "https://d.com/ad-x?foo=bar1&k=2", RT.DOCUMENT, "d.com")[1] == "https://d.com/ad-x?k=2", "rp regex _")
    check(e.page_flags("https://cos.com/", "cos.com") == nf.GHIDE, "ghide+type -> flags")
    e2, d2 = eng("*%2Ftwitter.com%2Fscribe%2Fibis%3F*$image\n/\\/x%2Fbanner%2F/\n# hosts comment\n#")
    check(M(e2, "https://mail.com/proxy?u=https%3A%2F%2Ftwitter.com%2Fscribe%2Fibis%3Fx", RT.IMAGE), "%XX pattern")
    check(M(e2, "https://a.com/x%2fBanner%2F1"), "%XX regex")
    check(d2["sets"]["B"][3] == {} and "twitter" in d2["sets"]["B"][1], "%XX patterns tokenized")
    check(d2["stats"]["accepted"] == 2, "'#' lines are comments")
    toks = nf._regex_tokens(r"^https?:\/\/[a-z]{8,15}\.com\/[a-z]+\.js$")
    check(set(toks) == {"com", "js"}, "regex tokens %r" % toks)
    check(nf._regex_tokens(r"ads?\/x") == [] or "ads" not in nf._regex_tokens(r"ads?\/x"), "regex optional")
    check(nf._regex_tokens(r"(a|b)\/banner\/") == ["banner"], "regex group")
    check(nf._regex_tokens(r"foo|bar") == [], "regex alternation")


def _ref_match(pat, url):
    """reference semantics via regex (only for short strings)"""
    anch = 0
    p = pat
    if p.startswith("||"):
        anch, p = 1, p[2:]
    elif p.startswith("|"):
        anch, p = 2, p[1:]
    right = p.endswith("|")
    if right:
        p = p[:-1]
    body = "".join(".*" if c == "*" else r"(?:[^0-9a-z_.%\-]|\Z)" if c == "^" else re.escape(c) for c in p)
    body += r"\Z" if right else ""
    if anch == 2:
        return re.match(body, url, re.S) is not None
    if anch == 1:
        hs, he = nf._host_span(url)
        starts = [hs] + [i + 1 for i in range(hs, he) if url[i] == "."]
        return any(re.match(body, url[s:], re.S) and True for s in starts) if not right else \
            any(re.match(body, url[s:], re.S) for s in starts)
    return re.search(body, url, re.S) is not None


def test_random_differential():
    import random
    rnd = random.Random(1234)
    alpha = "ab/.-*^?="
    bad = 0
    for _ in range(4000):
        core = "".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 7)))
        pre = rnd.choice(["", "", "|", "||"])
        if pre == "|":
            core = "https://" + core if rnd.random() < .5 else core
        pat = pre + core + rnd.choice(["", "", "|"])
        if len(pat) > 2 and pat[0] == "/" and pat[-1] == "/":
            continue                     # "/.../" is a regex filter by definition
        url = "https://" + "".join(rnd.choice("ab.") for _ in range(rnd.randint(1, 6))).strip(".") + "/" + \
              "".join(rnd.choice("ab/.-?=&") for _ in range(rnd.randint(0, 12)))
        e, d = eng(pat)
        if d["stats"]["accepted"] != 1 or d["stats"]["hosts"]:
            continue
        got = M(e, url, RT.SCRIPT, fp=nf._host_of(url)) is not None
        p2 = pat.lower()
        while "**" in p2:
            p2 = p2.replace("**", "*")
        exp = _ref_match(p2, url)
        if got != exp:
            bad += 1
            if bad <= 5:
                print("  diff:", repr(pat), url, "got", got, "exp", exp)
    check(bad == 0, "random differential matcher (%d diffs)" % bad)


def test_long_urls():
    _, d = eng("/(a+)+b/\n/(x\\/[a-z]*)+y/\n/(?:ab)+c/")
    check(d["stats"]["by_set"]["B"] == 1 and d["stats"]["skipped_options"].get("invalid:regex-redos") == 2,
          "nested-quantifier regex dropped %r" % d["stats"]["skipped_options"])
    e, _ = eng("""
/*BANER-BOHEMA-*.jpg$image
/*JmVu.js?sp=
/a^a^a^b
^ad^x
||ad*.example.com^
/(a+)+b/
/\\/x\\/[a-z0-9]+\\/y/
""")
    worst = 0.0
    for n in (4096, 16384, 65536):
        for u in ("https://ex.com/" + "a" * n, "https://ex.com/" + "a/" * (n // 2), "https://ex.com/" + "-a" * (n // 2),
                  "https://ex.com/?" + "a=1&" * (n // 4), "https://ad.example.com/" + "ad^" * (n // 3),
                  "https://ex.com/" + "a^" * (n // 2), "https://ex.com/" + "BANER-BOHEMA-" * (n // 13),
                  "https://ex.com/" + "/x/" * (n // 3)):
            for rt in (RT.IMAGE, RT.SCRIPT, RT.DOCUMENT):
                t = time.perf_counter()
                M(e, u, rt)
                worst = max(worst, time.perf_counter() - t)
    print("long-URL worst call: %.2f ms" % (worst * 1000))
    check(worst < 0.005, "64 KB URL call < 5 ms (got %.2f ms)" % (worst * 1000))


# ------------------------------------------------------------------ real lists
TRUE = {"ext_ublock", "env_chromium", "cap_user_stylesheet", "adguard_ext_chromium", "adguard_ext_opera"}
_COSM = re.compile(r"#@?[?$%]?\??#|#@?\$\??#")


def _eval(expr):
    toks = re.findall(r"!|&&|\|\||\(|\)|[A-Za-z0-9_]+", expr)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def atom():
        t = peek(); pos[0] += 1
        if t == "!":
            return not atom()
        if t == "(":
            v = orx()
            if peek() == ")":
                pos[0] += 1
            return v
        return t in TRUE

    def andx():
        v = atom()
        while peek() == "&&":
            pos[0] += 1; v = atom() and v
        return v

    def orx():
        v = andx()
        while peek() == "||":
            pos[0] += 1; v = andx() or v
        return v
    return orx() if toks else False


def read_list(path, inc_dir=None, depth=0):
    """minimal preprocessor + include + network-line splitter (test-only stand-in for compiler.py)"""
    stack = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            s = raw.strip()
            if s.startswith("!#if"):
                stack.append(_eval(s[4:]) and all(stack)); continue
            if s.startswith("!#else"):
                if stack:
                    parent = all(stack[:-1])
                    stack[-1] = parent and not stack[-1]
                continue
            if s.startswith("!#endif"):
                if stack:
                    stack.pop()
                continue
            if stack and not all(stack):
                continue
            if s.startswith("!#include"):
                name = s[9:].strip()
                if inc_dir and "/" not in name and "\\" not in name and depth < 2:
                    p = os.path.join(inc_dir, name)
                    if os.path.exists(p):
                        yield from read_list(p, inc_dir, depth + 1)
                continue
            if not s or s[0] in "![" or len(s) > 8192:
                continue
            m = re.match(r"(?:0\.0\.0\.0|127\.0\.0\.1)\s+(\S+)", s)
            if m:
                h = m.group(1).lower()
                if h not in ("0.0.0.0", "localhost", "127.0.0.1", "local") and "." in h:
                    yield "||" + h + "^"
                continue
            if _COSM.search(s):
                continue
            yield s


LISTS = [
    ("ubo-filters", r"lists\dl\ubo_filters_min_cdn\filters.min.txt", None),
    ("ubo-badware", r"lists\dl\ubo_badware_min_cdn\badware.min.txt", None),
    ("ubo-privacy", r"lists\dl\ubo_privacy_min_cdn\privacy.min.txt", None),
    ("ubo-quick-fixes", r"lists\dl\ubo_quick_fixes_min_cdn\quick-fixes.min.txt", None),
    ("ubo-unbreak", r"lists\dl\ubo_unbreak_min_cdn\unbreak.min.txt", None),
    ("easylist", r"lists\dl\easylist_uassetscdn_ghpages\easylist.txt", None),
    ("easyprivacy", r"lists\dl\easyprivacy_uassetscdn_ghpages\easyprivacy.txt", None),
    ("pgl", r"lists\dl\plowe_hosts\serverlist.php.txt", None),
    ("pol0", r"lists\dl\pol0_majkiit\adblock.txt", r"lists\dl\pol0_majkiit__inc"),
]
QT2RT = {"MainFrame": RT.DOCUMENT, "SubFrame": RT.SUBDOCUMENT, "Stylesheet": RT.STYLESHEET, "Script": RT.SCRIPT,
         "Image": RT.IMAGE, "FontResource": RT.FONT, "SubResource": RT.OTHER, "Object": RT.OBJECT,
         "Media": RT.MEDIA, "Worker": RT.SCRIPT, "SharedWorker": RT.SCRIPT, "ServiceWorker": RT.SCRIPT,
         "Prefetch": RT.OTHER, "Favicon": RT.IMAGE, "Xhr": RT.XHR, "Ping": RT.PING, "CspReport": RT.OTHER,
         "PluginResource": RT.OBJECT, "WebSocket": RT.WEBSOCKET, "Json": RT.XHR}


def _host(url):
    h = nf._host_of(url)
    try:
        return h.encode("idna").decode() if not h.isascii() else h
    except Exception:
        return h


def bench():
    paths = [(lid, os.path.join(SCR, p), os.path.join(SCR, inc) if inc else None) for lid, p, inc in LISTS]
    corpus_p = os.path.join(SCR, "critic", "c6_corpus.json")
    if not all(os.path.exists(p) for _, p, _ in paths) or not os.path.exists(corpus_p):
        print("benchmark skipped: lists/corpus not found under", SCR)
        return
    items = []
    for lid, p, inc in paths:
        items.extend((l, lid, lid.startswith("ubo-")) for l in read_list(p, inc))
    t = time.perf_counter()
    d = compile_network(items)
    tc = time.perf_counter() - t
    blob = marshal.dumps(d)
    st = d["stats"]
    print("network lines %d, accepted %d (hashed hosts %d), dup %d, badfiltered %d, unsupported %d, unknown %d, "
          "invalid %d; compile %.2f s; net.bin %.2f MB" % (st["lines"], st["accepted"], st["hosts"], st["duplicates"],
                                                          st["badfiltered"], st["unsupported"], st["unknown"],
                                                          st["invalid"], tc, len(blob) / 1e6))
    print("by set:", st["by_set"])
    top = sorted(st["skipped_options"].items(), key=lambda kv: -kv[1])[:12]
    print("skipped:", top)
    del d
    gc.collect()
    # load time (marshal.loads + from_dict) and resident size
    lt = []
    for _ in range(5):
        gc.collect()
        t = time.perf_counter()
        e = NetEngine.from_dict(marshal.loads(blob))
        lt.append(time.perf_counter() - t)
        del e
    gc.collect()
    tracemalloc.start()
    e = NetEngine.from_dict(marshal.loads(blob))
    gc.collect()
    mem = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    load_ms = statistics.median(lt) * 1000
    print("load median %.1f ms (min %.1f), resident %.1f MB" % (load_ms, min(lt) * 1000, mem / 1e6))
    check(load_ms <= 60, "load <= 60 ms (%.1f)" % load_ms)
    check(mem <= 25e6, "resident <= 25 MB (%.1f)" % (mem / 1e6))
    corpus = json.load(open(corpus_p, encoding="utf-8"))
    reqs = []
    for site, url, typ, fp, ini, meth in corpus:
        fpu = fp or site
        reqs.append((url, _host(url), _host(fpu), QT2RT.get(typ.replace("ResourceType", ""), RT.OTHER), meth, fpu))
    gc.freeze()
    res = None
    per = []
    for rep in range(4):
        if rep == 3:
            e._hc.clear()           # last rep: cold host cache (regex/segment caches stay warm)
        per = []
        res = []
        match = e.match
        pc = time.perf_counter_ns
        for url, h, fh, rt, meth, fpu in reqs:
            t0 = pc()
            r = match(url, h, fh, rt, meth, fpu)
            per.append((pc() - t0) / 1000)
            res.append(r)
        if rep == 0:
            first = sorted(per)
    s = sorted(per)
    q = lambda arr, p: arr[min(len(arr) - 1, int(len(arr) * p))]
    med, p99, mx = q(s, .5), q(s, .99), s[-1]
    print("corpus %d requests: median %.1f us, mean %.1f, p90 %.1f, p99 %.1f, max %.1f us  (first/cold pass: median "
          "%.1f, p99 %.1f, max %.1f)" % (len(s), med, statistics.mean(s), q(s, .9), p99, mx, q(first, .5),
                                         q(first, .99), first[-1]))
    dec = {}
    for r in res:
        k = r[0] if r else "allow"
        dec[k] = dec.get(k, 0) + 1
    print("decisions:", dec)
    check(med <= 50, "median <= 50 us (%.1f)" % med)
    check(p99 <= 400, "p99 <= 400 us (%.1f)" % p99)
    check(mx <= 5000, "max <= 5 ms (%.1f us)" % mx)
    # sanity on well-known ad/tracker URLs
    for url, rt, fp in [("https://securepubads.g.doubleclick.net/tag/js/gpt.js", RT.SCRIPT, "www.onet.pl"),
                        ("https://www.google-analytics.com/analytics.js", RT.SCRIPT, "www.wp.pl"),
                        ("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js", RT.SCRIPT, "x.pl")]:
        r = e.match(url, _host(url), fp, rt)
        print("  ", url, "->", r)
        check(r is not None, "known ad blocked: " + url)
    check(e.match("https://www.onet.pl/", "www.onet.pl", "www.onet.pl", RT.DOCUMENT) is None, "onet doc allowed")
    print("page_flags youtube:", e.page_flags("https://www.youtube.com/", "www.youtube.com"),
          "wp.pl:", e.page_flags("https://www.wp.pl/", "www.wp.pl"))
    # long URLs against the full engine
    worst = 0.0
    for n in (4096, 65536):
        for u in ("https://www.wp.pl/" + "a" * n, "https://ex.com/" + "a/" * (n // 2), "https://ex.com/?" + "a=1&" * (n // 4),
                  "https://ad.ex.com/" + "-ad-" * (n // 4), "https://ex.com/" + "BANER-BOHEMA-" * (n // 13)):
            for rt in (RT.IMAGE, RT.SCRIPT, RT.SUBDOCUMENT, RT.DOCUMENT):
                t = time.perf_counter()
                e.match(u, _host(u), "www.wp.pl", rt)
                worst = max(worst, time.perf_counter() - t)
    print("full engine long-URL worst: %.2f ms" % (worst * 1000))
    check(worst < 0.005, "full engine 64 KB URL < 5 ms (%.2f ms)" % (worst * 1000))
    gc.unfreeze()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if "--no-bench" not in sys.argv:
        bench()
    print("%d checks, %d failed" % (COUNT[0], len(FAILS)))
    sys.exit(1 if FAILS else 0)
