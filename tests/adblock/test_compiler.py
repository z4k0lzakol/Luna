"""Tests for adblock.compiler / adblock.psl / adblock.catalog.  Run: python -I tests/adblock/test_compiler.py"""
import json
import marshal
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import types

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from adblock import catalog, compiler, psl  # noqa: E402

FAILS = []
PASSES = [0]


def check(cond, msg):
    if cond:
        PASSES[0] += 1
    else:
        FAILS.append(msg)
        print("FAIL:", msg)


def eq(a, b, msg):
    check(a == b, "%s: %r != %r" % (msg, a, b))


# a stub network compiler (the real one is adblock/netfilter.py, ENGINE-B)
STUB_NET = types.SimpleNamespace(compile_network=lambda items: {"stub": [t for t, _l, _tr in items]})


# ---------------------------------------------------------------- preprocessor
def test_preprocessor():
    ev = compiler.eval_cond
    check(ev("ext_ublock"), "token true")
    check(not ev("cap_html_filtering"), "html filtering false")
    check(not ev("unknown_token"), "unknown false")
    check(ev("!ext_ubol"), "negation")
    check(ev("env_chromium && !env_mobile"), "and")
    check(ev("env_firefox || env_chromium"), "or")
    check(not ev("(env_firefox || env_safari) && ext_ublock"), "parens")
    check(ev("!(env_firefox || env_safari) && ext_ublock"), "not parens")
    check(not ev("env_chromium &&"), "syntax error -> false")
    text = "\n".join([
        "a", "!#if env_firefox", "b", "!#if ext_ublock", "c", "!#endif", "!#else", "d",
        "!#if cap_html_filtering", "e", "!#else", "f", "!#endif", "!#endif", "!#include inc.txt",
        "!#include ../evil.txt", "!#if false", "!#include inc.txt", "!#endif", "! comment", "  g  "])
    incs = {"inc.txt": "x1\n!#if ext_ublock\nx2\n!#endif\n"}
    out = compiler.preprocess(text, lambda n: incs.get(n) if compiler._safe_include_name(n) else None)
    eq(out, ["a", "d", "f", "x1", "x2", "! comment", "g"], "preprocess")


# ---------------------------------------------------------------- scriptlet args
def test_split_args():
    S = compiler.split_args
    eq(S("nowoif"), ["nowoif"], "1")
    eq(S("aeld, , preventDefault"), ["aeld", "", "preventDefault"], "2")
    eq(S("nostif, ).show()"), ["nostif", ").show()"], "3")
    eq(S("acs, Math, '0x"), ["acs", "Math", "'0x"], "4")
    eq(S("set, foo, ''"), ["set", "foo", ""], "5")
    eq(S("set, art3m1sItemNames.affiliate-wrapper, '\"\"'"), ["set", "art3m1sItemNames.affiliate-wrapper", '""'], "6")
    eq(S('acs, jQuery, "No"'), ["acs", "jQuery", "No"], "7")
    eq(S("m3u-prune, /#EXT-X-DISCONTINUITY.{1\\,100}#EXT-X-DISCONTINUITY/gm, mixed.m3u8"),
       ["m3u-prune", "/#EXT-X-DISCONTINUITY.{1,100}#EXT-X-DISCONTINUITY/gm", "mixed.m3u8"], "8")
    eq(S("trusted-click-element, 'a, b', , 1000"), ["trusted-click-element", "a, b", "", "1000"], "9")
    eq(S('rpnt, script, "adBlockWallEnabled":true, "adBlockWallEnabled":false'),
       ["rpnt", "script", '"adBlockWallEnabled":true', '"adBlockWallEnabled":false'], "10")
    eq(S("aeld, , '\\'"), ["aeld", "", "'\\'"], "11")
    eq(S("trusted-set, prop, '{ \"value\": [ \"one\", \"two\", 3 ]}'"),
       ["trusted-set", "prop", '{ "value": [ "one", "two", 3 ]}'], "12")
    eq(S("set, foo, "), ["set", "foo", ""], "trailing comma")


# ---------------------------------------------------------------- selectors
def test_selectors():
    C = compiler.compile_selector
    eq(C(".ad"), ("hide", ".ad"), "plain")
    eq(C("div:has(> a.x):not(.y)"), ("hide", "div:has(> a.x):not(.y)"), "native has/not")
    eq(C("div:-abp-has(.x)"), ("hide", "div:has(.x)"), "abp-has -> native")
    eq(C("body:style(overflow:auto !important)"), ("style", "body", "overflow:auto !important"), "style")
    eq(C("#nitro-block:style(position:absolute; left:-3000px)"),
       ("style", "#nitro-block", "position:absolute; left:-3000px"), "style 2 decls")
    eq(C(".x:remove()"), ("remove", ".x"), "remove")
    r = C("a[onclick]:remove-attr(onclick)")
    eq(r, ("proc", {"s": "a[onclick]:remove-attr(onclick)", "t": [["css", "a[onclick]"]],
                    "a": ["remove-attr", {"r": "^onclick$", "f": ""}]}), "remove-attr")
    r = C("div.ad:has-text(/Sponsored/i):upward(2)")
    eq(r[1]["t"], [["css", "div.ad"], ["has-text", {"r": "Sponsored", "f": "i"}], ["upward", 2]], "has-text upward")
    r = C(':matches-path(/^/home/) [data-testid="primaryColumn"]:others()')
    eq(r[1]["t"], [["matches-path", {"r": "^/home", "f": ""}], ["css", '[data-testid="primaryColumn"]'],
                   ["others"]], "matches-path others")
    r = C("div:has(> span:has-text(Ad))")
    eq(r[1]["t"], [["css", "div"], ["has", [["css", "> span"], ["has-text", {"t": "Ad"}]]]], "procedural has")
    r = C("div:has(:has(a))")
    eq(r[1]["t"], [["css", "div"], ["has", [["css", ":has(a)"]]]], "nested has -> proc")
    r = C("div:has(:scope > a)")
    eq(r[0], "proc", ":scope in has -> proc")
    r = C('div[class^="_"]:matches-css(background-image: /^url\\("data:image\\/png;base64,/)')
    eq(r[1]["t"][1], ["matches-css", None, "background-image", {"r": '^url\\("data:image\\/png;base64,', "f": ""}],
       "matches-css regex")
    r = C("div:matches-css-after(content:/R.*E.*K.*L.*A.*M.*A/):upward(1)")
    eq(r[1]["t"][1], ["matches-css", "after", "content", {"r": "R.*E.*K.*L.*A.*M.*A", "f": ""}], "css-after")
    r = C('button:matches-attr(class="/[\\w]{7}/")')
    eq(r[1]["t"][1], ["matches-attr", {"r": "^class$", "f": ""}, {"r": "[\\w]{7}", "f": ""}], "matches-attr")
    r = C("div:not(:has-text(Promoted))")
    eq(r[1]["t"], [["css", "div"], ["not", [["has-text", {"t": "Promoted"}]]]], "not procedural")
    r = C("div:not(.a:has-text(x))")
    eq(r[1]["t"][1], ["not", [["matches", ".a"], ["has-text", {"t": "x"}]]], "not compound")
    r = C("a:has-text(x) + b")
    eq(r[1]["t"], [["css", "a"], ["has-text", {"t": "x"}], ["spath", " + b"]], "spath sibling")
    r = C("span:has-text(x):upward(2).foo > i")
    eq(r[1]["t"][2:], [["upward", 2], ["matches", ".foo"], ["spath", " > i"]], "compound after op")
    r = C(":xpath(//div[@id=\"x\"])")
    eq(r[1]["t"], [["xpath", '//div[@id="x"]']], "xpath start")
    r = C(":has-text(foo)")
    eq(r[1]["t"], [["css", "*"], ["has-text", {"t": "foo"}]], "leading op gets *")
    r = C("pre:matches-media(print):style(white-space:pre-line !important;)")
    eq(r[1], {"s": "pre:matches-media(print):style(white-space:pre-line !important;)",
              "t": [["css", "pre"], ["matches-media", "print"]],
              "a": ["style", "white-space:pre-line !important;"]}, "matches-media style")
    r = C('.j-mini-player[class]:watch-attr(class):remove-attr(class)')
    eq(r[1]["t"][1], ["watch-attr", ["class"]], "watch-attr")
    r = C('html[x]:remove-class(/^cookie/)')
    eq(r[1]["a"], ["remove-class", {"r": "^cookie", "f": ""}], "remove-class regex")
    r = C(".x:has-text(\"a)b\")")
    eq(r[1]["t"][1], ["has-text", {"t": "a)b"}], "quoted paren")
    r = C(".x:has-text(/(a|b)\\)/)")
    eq(r[1]["t"][1], ["has-text", {"r": "(a|b)\\)", "f": ""}], "regex with escaped paren")
    r = C(".x:has-text(Don't)")
    eq(r[1]["t"][1], ["has-text", {"t": "Don't"}], "unterminated quote in text")
    r = C(".x", forced=True)
    eq(r, ("proc", {"s": ".x", "t": [["css", ".x"]]}), "#?# forced")
    r = C("div:-abp-has(.x)", forced=True)
    eq(r[1]["t"], [["css", "div"], ["has", [["css", ".x"]]]], "#?# has stays procedural")
    r = C("div:if-not(.x)")
    eq(r[1]["t"][1], ["not", [["has", [["css", ".x"]]]]], "if-not")
    r = C(":not(:matches-path(/fanza/)) section:has(> a)")
    eq(r[1]["t"], [["css", "html"], ["not", [["matches-path", {"r": "fanza", "f": ""}]]],
                   ["spath", " section:has(> a)"]], "negated path gate")
    try:
        C(":not(:matches-path(/fanza/)) ")
        check(False, "bare negated gate must be invalid")
    except compiler.Invalid:
        PASSES[0] += 1
    r = C("div:min-text-length(100)")
    eq(r[1]["t"][1], ["min-text-length", 100], "min-text-length")
    r = C("div:upward(.wrap)")
    eq(r[1]["t"][1], ["upward", ".wrap"], "upward css")
    # invalid / unsupported
    for bad in ["div {color:red}", "a;b", "@import x", ".a /* x */", "a[href", "a)", ".x:style(background:url(x))",
                ".x:style(color:red} body{x:y)", ".x:remove(1)", ".x:remove():has-text(a)", "div:upward(0)",
                ".x:style(a: b \\ c)", ":style(color:red)", ".x:has-text(a):style(a://b)"]:
        try:
            C(bad)
            check(False, "should be invalid: " + bad)
        except (compiler.Invalid, compiler.Unsupported):
            PASSES[0] += 1
    try:
        C("div:-abp-properties(width:300px)")
        check(False, "abp-properties")
    except compiler.Unsupported:
        PASSES[0] += 1
    check(compiler.valid_css('a[title="{x}"]'), "brace inside quotes ok")
    check(not compiler.valid_css('a{x}'), "brace outside quotes")


def test_lowly():
    L = compiler.lowly_key
    eq(L(".ad"), ".ad", "class")
    eq(L("#banner"), "#banner", "id")
    eq(L("div > .foo .bar"), ".bar", "rightmost")
    eq(L(".a .b#c"), "#c", "prefer id")
    eq(L('[id^="div-gpt-ad"]'), None, "attr -> high")
    eq(L('a[href*=".com"]'), None, "dot in attr")
    eq(L(".x:not(.y)"), ".x", "not ignored")
    eq(L("div:not(.y)"), None, "only inside not")
    eq(compiler.split_top('.a, .b[title="x, y"], .c'), [".a", '.b[title="x, y"]', ".c"], "split_top")


# ---------------------------------------------------------------- builder / site.db
def _build(lines, trusted=False, list_id="t"):
    b = compiler.Builder()
    for ln in compiler.preprocess("\n".join(lines)):
        b.add(ln, list_id, trusted)
    site = {k: json.loads(v) for k, v in b.site_rows()}
    return b, site


def test_builder():
    b, site = _build([
        "! comment",
        "[Adblock Plus 2.0]",
        "127.0.0.1 ads.example.com",
        "0.0.0.0 tracker.example.net other.example.org # c",
        "0.0.0.0 localhost",
        "||doubleclick.net^",
        "@@||good.com^$ghide",
        "/banner/*/img^",
        "example.com,~sub.example.com##.ad",
        "example.*##.ent",
        "~skip.com##.gen",
        "##.generic",
        "###gid",
        '##[id^="div-gpt-ad"]',
        "##.a, .b",
        "#@#.gen2",
        "*##.everywhere",
        "##div:has-text(x)",
        "example.com#@#.ad",
        "example.com##+js(set, foo, true)",
        "example.com##+js(nostif.js, /adb/)",
        "example.com#@#+js(set, foo, true)",
        "example.com#@#+js()",
        "example.com,~a.example.com##+js(aopr, x)",
        "tomsguide.com>>##+js(trusted-click-element, button)",
        "example.com##+js(trusted-set-cookie, a, b)",
        "##+js(aopr, generic)",
        "example.com##^script:has-text(x)",
        "example.com#$#.x { display:none }",
        "example.com#%#//scriptlet('abort-on-property-read', 'x')",
        "example.com$$script[tag-content=\"x\"]",
        "/^regex\\.com$/##.r",
        "żółć.pl##.idn",
        "example.com##.x:style(color:red)",
        "example.com#?#.y",
        "example.com##.z:has-text(/a/i)",
        "example.com#@#.z:has-text(/a/i)",
        "example.com##.r:remove()",
        "example.com##+js()",
        "example.com/path##.p",
        "# hosts comment",
        "[$path=/x]example.com##.m",
    ])
    nets = [t for t, _l, _tr in b.net]
    eq(nets, ["||ads.example.com^", "||tracker.example.net^", "||other.example.org^", "||doubleclick.net^",
              "@@||good.com^$ghide", "/banner/*/img^"], "network items")
    eq(site["example.com"]["hide"], [".ad"], "specific hide")
    eq(site["sub.example.com"]["unhide"], [".ad"], "negation -> unhide")
    eq(site["example.*"]["hide"], [".ent"], "entity")
    eq(site["skip.com"]["unhide"], [".gen"], "generic negation")
    cos = b.cos_dict()
    check(".generic" in cos["lowly"] and "#gid" in cos["lowly"] and ".gen" in cos["lowly"], "lowly keys")
    check('[id^="div-gpt-ad"]' in cos["high"] and ".everywhere" in cos["high"], "high")
    check(".a" in cos["lowly"] and ".b" in cos["lowly"], "comma split")
    eq(cos["unhide"], [".gen2"], "generic unhide")
    check(b.dropped.get("generic_procedural") == 1, "generic procedural dropped")
    eq(site["example.com"]["unhide"], [".ad", ".z:has-text(/a/i)"], "specific unhide")
    eq(site["example.com"]["js"], [["set-constant", ["foo", "true"], False],
                                   ["prevent-setTimeout", ["/adb/"], False],
                                   ["abort-on-property-read", ["x"], False]], "js alias resolution")
    eq(site["example.com"]["unjs"], [["set-constant", ["foo", "true"]], ["*"]], "unjs")
    eq(site["a.example.com"]["unjs"], [["abort-on-property-read", ["x"]]], "js negation")
    check(">>tomsguide.com" not in site, "untrusted trusted-* dropped")
    check(b.dropped.get("js_untrusted") == 2, "js_untrusted count")
    check(b.dropped.get("js_generic") == 1, "generic js ignored")
    check(b.dropped.get("html_filter") == 2, "html filters skipped")
    check(b.dropped.get("adguard_js") == 1, "adguard js skipped")
    check("xn--kda4b0koi.pl" in site or any(k.startswith("xn--") for k in site), "idn punycode")
    eq(site["example.com"]["style"], [[".x", "display:none"], [".x", "color:red"]], "style (+#$# converted)")
    eq(site["/^regex\\.com$/"]["hide"], [".r"], "regex host row")
    eq(site["/"], {"re": ["/^regex\\.com$/"]}, "regex index row")
    b4, site4 = _build(["a.com##.s {remove:true;}", "a.com##.t {top:0 !important;}", "a.com##.u {x:url(y)}"])
    eq(site4["a.com"].get("remove"), [".s"], "abp css injection remove")
    eq(site4["a.com"].get("style"), [[".t", "top:0 !important;"]], "abp css injection style")
    check(b4.dropped.get("cos_invalid") == 1, "css injection sanitized")
    eq(site["example.com"]["proc"][0], {"s": ".y", "t": [["css", ".y"]]}, "#?#")
    eq(site["example.com"]["proc"][1]["t"][1], ["has-text", {"r": "a", "f": "i"}], "proc")
    eq(site["example.com"]["remove"], [".r"], "remove")
    check(b.dropped.get("js_empty") == 1, "empty +js")
    check(b.dropped.get("bad_hostname", 0) == 1, "path-target host dropped")
    check(b.dropped.get("adguard_modifier") == 1, "[$path] skipped")
    # trusted list keeps trusted-* and ancestor keys
    b2, site2 = _build(["tomsguide.com>>##+js(trusted-click-element, button)",
                        "x.com##+js(trusted-set-cookie, a, b)"], trusted=True)
    eq(site2[">>tomsguide.com"]["js"], [["trusted-click-element", ["button"], True]], "ancestor trusted")
    eq(site2["x.com"]["js"][0][2], True, "trusted flag")
    # unsafe set-attr
    b3, site3 = _build(["x.com##+js(set-attr, a, onclick, alert(1))"])
    check("x.com" not in site3 and b3.dropped.get("js_unsafe") == 1, "set-attr on* dropped")


# ---------------------------------------------------------------- psl
PSL_TEXT = """// comment
com
co.uk
uk
*.ck
!www.ck
jp
kawasaki.jp
*.kawasaki.jp
!city.kawasaki.jp
github.io
pl
waw.pl
// unicode
公司.cn
cn
"""


def test_psl():
    d = psl.parse(PSL_TEXT)
    p = psl.PSL(d)
    eq(p.public_suffix("www.example.com"), "com", "com")
    eq(p.registrable("a.b.example.co.uk"), "example.co.uk", "co.uk")
    eq(p.registrable("foo.bar.ck"), "foo.bar.ck", "wildcard")
    eq(p.public_suffix("bar.ck"), "bar.ck", "wildcard ps")
    eq(p.registrable("www.ck"), "www.ck", "exception")
    eq(p.public_suffix("a.www.ck"), "ck", "exception ps")
    eq(p.registrable("a.b.kawasaki.jp"), "a.b.kawasaki.jp", "wild jp")
    eq(p.registrable("x.city.kawasaki.jp"), "city.kawasaki.jp", "exception jp")
    eq(p.registrable("user.github.io"), "user.github.io", "private section")
    eq(p.registrable("um.waw.pl"), "um.waw.pl", "waw.pl")
    eq(p.registrable("foo.unknowntld"), "foo.unknowntld", "default rule")
    eq(p.registrable("1.2.3.4"), "1.2.3.4", "ip")
    eq(p.registrable("com"), "com", "bare suffix")
    check("xn--55qx5d.cn" in d, "idna rule")
    eq(p.entity_keys("b.example.co.uk"), ["example.*", "b.example.*"], "entity keys")
    eq(p.entity_keys("www.google.com"), ["google.*", "www.google.*"], "entity keys 2")
    eq(p.entity_keys("co.uk"), [], "entity keys ps")
    h = psl.PSL(None)
    eq(h.registrable("news.bbc.co.uk"), "bbc.co.uk", "heuristic sld")
    eq(h.registrable("sklep.allegro.pl"), "allegro.pl", "heuristic")
    eq(h.entity_keys("a.b.example.com"), ["example.*", "b.example.*", "a.b.example.*"], "heuristic entity")
    tmp = tempfile.mkdtemp()
    try:
        pb = os.path.join(tmp, "psl.bin")
        with open(pb, "wb") as f:
            marshal.dump(d, f)
        eq(psl.PSL.load(pb).registrable("x.y.example.co.uk"), "example.co.uk", "load bin")
        pd = os.path.join(tmp, "p.dat")
        with open(pd, "w", encoding="utf-8") as f:
            f.write(PSL_TEXT)
        eq(psl.PSL.load(pd).registrable("x.y.example.co.uk"), "example.co.uk", "load dat")
        check(psl.PSL.load(os.path.join(tmp, "missing")).data is None, "missing -> heuristic")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- catalog
def test_catalog():
    ids = [l["id"] for l in catalog.LISTS]
    for i in ["ubo-filters", "ubo-badware", "ubo-privacy", "ubo-quick-fixes", "ubo-unbreak", "easylist",
              "easyprivacy", "pgl", "pol0", "hagezi-pro", "psl"]:
        check(i in ids, "catalog has " + i)
    hz = catalog.get("hagezi-pro")
    check(hz["url"].startswith("https://") and hz["fallback"].startswith("https://") and not hz["trusted"],
          "hagezi: https + fallback, untrusted")
    eq(catalog.get("ubo-quick-fixes")["expires_h"], 12, "quick fixes 12h")
    eq(catalog.get("ubo-filters")["fallback"], "https://ublockorigin.pages.dev/filters/filters.min.txt", "fallback")
    check(catalog.get("ubo-filters")["trusted"] and not catalog.get("easylist")["trusted"], "trust")
    eq(catalog.include_url(catalog.get("pol0"), "adblock_ublock.txt"),
       "https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock_ublock.txt",
       "include url")
    eq(catalog.include_url(catalog.get("pol0"), "../x.txt"), None, "include traversal")
    eq(catalog.enabled_ids({"pgl": False}), [i for i in ids if i not in ("pgl", "psl")], "enabled ids")
    home = tempfile.mkdtemp()
    try:
        os.makedirs(catalog.lists_dir(home))
        for i in ("ubo-filters", "pol0", "psl"):
            open(catalog.list_path(i, home), "w").close()
        open(catalog.include_path("pol0", "adblock_ublock.txt", home), "w").close()
        cfg = catalog.build_config(["ubo-filters", "pol0", "easylist"], "x", home)
        eq([l["id"] for l in cfg["lists"]], ["ubo-filters", "pol0"], "config lists")
        eq(cfg["lists"][1]["includes"], [catalog.include_path("pol0", "adblock_ublock.txt", home)], "config inc")
        check(cfg["psl"] and cfg["lists"][0]["trusted"], "config psl/trusted")
        meta = {"ubo-filters": {"fetched": 1000}}
        check(catalog.is_expired("ubo-filters", meta, now=1000 + 121 * 3600, home=home), "expired")
        check(not catalog.is_expired("ubo-filters", meta, now=1000 + 3600, home=home), "fresh")
        check(catalog.is_expired("pol0", meta, home=home), "never fetched")
        eq(catalog.next_expiry(["ubo-filters"], meta, now=1000), 120 * 3600.0, "next expiry")
        catalog.save_meta(meta, home)
        eq(catalog.load_meta(home), meta, "meta roundtrip")
    finally:
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- end to end (CLI, subprocess)
def test_end_to_end():
    tmp = tempfile.mkdtemp()
    try:
        ld = os.path.join(tmp, "lists")
        os.makedirs(ld)
        with open(os.path.join(ld, "a.txt"), "w", encoding="utf-8") as f:
            f.write("! x\n||ads.com^\nexample.com##.ad\n##.gen\n!#include inc.txt\n!#include ../x.txt\n"
                    "!#if cap_html_filtering\n||html.com^\n!#endif\n" + "x" * 9000 + "\n")
        with open(os.path.join(ld, "a__inc.txt"), "w", encoding="utf-8") as f:
            f.write("inc.com##+js(set, a, 1)\n")
        with open(os.path.join(ld, "psl.dat"), "w", encoding="utf-8") as f:
            f.write(PSL_TEXT)
        cfg = {"lists": [{"id": "a", "path": os.path.join(ld, "a.txt"), "trusted": False,
                          "includes": [os.path.join(ld, "a__inc.txt")]},
                         {"id": "missing", "path": os.path.join(ld, "nope.txt"), "trusted": False, "includes": []}],
               "user": "user.com##.u\n", "psl": os.path.join(ld, "psl.dat")}
        cp = os.path.join(tmp, "config.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        out = os.path.join(tmp, "build-1")
        # the stub network compiler is injected through a tiny shim module on sys.path (outside the repo)
        shim = os.path.join(tmp, "shim")
        os.makedirs(shim)
        with open(os.path.join(shim, "run.py"), "w", encoding="utf-8") as f:
            f.write("import sys, types\nsys.path.insert(0, %r)\n" % REPO +
                    "from adblock import compiler\n"
                    "try:\n    from adblock import netfilter\nexcept Exception:\n"
                    "    netfilter = types.SimpleNamespace(compile_network=lambda it: {'stub': [t for t, l, tr in it]})\n"
                    "_orig = compiler.compile_lists\n"
                    "compiler.compile_lists = lambda cfg, out, ld=None, netfilter_=None: _orig(cfg, out, ld, netfilter)\n"
                    "compiler.main()\n")
        r = subprocess.run([sys.executable, "-I", os.path.join(shim, "run.py"), ld, out, cp],
                           capture_output=True, text=True, timeout=120)
        eq(r.returncode, 0, "exit code (stderr: %s)" % r.stderr[-500:])
        for fn in ("net.bin", "cos.bin", "site.db", "info.json", "psl.bin"):
            check(os.path.isfile(os.path.join(out, fn)), "output " + fn)
        check(not os.path.exists(out + ".tmp"), "tmp renamed")
        info = json.load(open(os.path.join(out, "info.json"), encoding="utf-8"))
        eq(info["format"], 1, "format")
        eq(info["counts"]["a"], 4, "counts a")
        eq(info["counts"]["user"], 1, "counts user")
        eq(info["counts"]["missing"], 0, "counts missing")
        eq(info["dropped"].get("line_too_long"), 1, "line cap")
        con = sqlite3.connect(os.path.join(out, "site.db"))
        rows = dict(con.execute("SELECT key, data FROM site").fetchall())
        con.close()
        eq(json.loads(rows["inc.com"])["js"], [["set-constant", ["a", "1"], False]], "include applied")
        check("user.com" in rows and "example.com" in rows, "rows")
        cos = marshal.load(open(os.path.join(out, "cos.bin"), "rb"))
        eq(cos["lowly"], {".gen": [".gen"]}, "cos lowly")
        p = psl.PSL.load(os.path.join(out, "psl.bin"))
        eq(p.registrable("a.b.example.co.uk"), "example.co.uk", "psl.bin")
        # failure path: bad config -> exit 1, no output dir
        r = subprocess.run([sys.executable, "-I", os.path.join(shim, "run.py"), ld, os.path.join(tmp, "b2"),
                            os.path.join(tmp, "nope.json")], capture_output=True, text=True, timeout=60)
        eq(r.returncode, 1, "bad config exit")
        check(not os.path.exists(os.path.join(tmp, "b2")), "no output on failure")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception:
                import traceback
                traceback.print_exc()
                FAILS.append(name + " raised")
    print("passed checks: %d, failed: %d" % (PASSES[0], len(FAILS)))
    sys.exit(1 if FAILS else 0)
