"""SCRIPTLETS-1 without Qt: name tables, scheme fake-body codec, bundle syntax (node --check) and the JSON engines
(lib-json: legacy json-prune paths + uBO-flavoured JSONPath) evaluated in node with a minimal R.
Run: python -I tests/adblock/test_scriptlets1.py          (node optional: JS parts are skipped without it)
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from adblock import scriptlet_names as names  # noqa: E402
from adblock import scriptlets  # noqa: E402

FAILS, COUNT = [], [0]


def check(cond, label, extra=None):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
        print("FAIL:", label, "" if extra is None else repr(extra)[:500])


MINE = {
    "prevent-fetch", "trusted-prevent-fetch", "prevent-xhr", "trusted-prevent-xhr",
    "json-prune", "json-prune-fetch-response", "json-prune-xhr-response",
    "jsonl-prune-fetch-response", "jsonl-prune-xhr-response",
    "trusted-replace-fetch-response", "trusted-replace-xhr-response",
    "trusted-prune-inbound-object", "trusted-prune-outbound-object",
    "json-edit", "trusted-json-edit", "json-edit-fetch-response", "json-edit-xhr-response",
    "json-edit-fetch-request", "json-edit-xhr-request", "jsonl-edit-fetch-response", "jsonl-edit-xhr-response",
    "trusted-json-edit-fetch-response", "trusted-json-edit-xhr-response", "trusted-json-edit-fetch-request",
    "trusted-json-edit-xhr-request", "trusted-jsonl-edit-fetch-response", "trusted-jsonl-edit-xhr-response",
    "edit-outbound-object", "edit-inbound-object", "edit-this-object", "edit-element-object",
    "edit-object-on-setter", "edit-object-on-getter", "trusted-edit-outbound-object", "trusted-edit-inbound-object",
    "trusted-edit-this-object", "trusted-edit-element-object", "trusted-edit-object-on-setter",
    "trusted-edit-object-on-getter", "xml-prune", "m3u-prune", "noeval", "noeval-silent", "noeval-if",
    "evaldata-prune", "nowebrtc",
}


def t_names():
    check(MINE <= names.KNOWN, "all SCRIPTLETS-1 names are KNOWN", sorted(MINE - names.KNOWN))
    check(MINE <= names.SUPPORTED, "all SCRIPTLETS-1 names SUPPORTED", sorted(MINE - names.SUPPORTED))
    check(MINE <= scriptlets.available(), "all have files", sorted(MINE - scriptlets.available()))
    c = names.canonical
    for a, cn in (("no-fetch-if", "prevent-fetch"), ("no-xhr-if", "prevent-xhr"), ("trusted-rpfr", "trusted-replace-fetch-response"),
                  ("prevent-eval-if", "noeval-if"), ("silent-noeval", "noeval-silent"), ("ubo-no-fetch-if.js", "prevent-fetch"),
                  ("json-prune.js", "json-prune")):
        check(c(a) == cn, "alias %s" % a, c(a))
    for t in ("trusted-prevent-fetch", "trusted-rpfr", "trusted-json-edit", "trusted-edit-inbound-object",
              "trusted-prune-outbound-object"):
        check(names.is_trusted_only(t), "trusted-only " + t)
    for u in ("json-edit", "edit-inbound-object", "xml-prune", "no-fetch-if"):
        check(not names.is_trusted_only(u), "not trusted-only " + u)
    b = scriptlets.build
    check(b([("trusted-json-edit", [".a=1"], False)], "x") is None, "trusted-json-edit from untrusted list dropped")
    check(b([("json-edit", [".a"], False)], "x") is not None, "json-edit from untrusted list kept")
    js = b([("trusted-rpfr", ["a", "b"], True), ("no-xhr-if", ["ads"], False)], "x", sr="xq://l/t/")
    check(js is not None and js.count("var a") >= 4, "deps bundled (lib-net + 2 scriptlets + dep)", js and js.count("var a"))
    check('"lib-net":' in js, "lib-net in deps map")


def t_fake_body():
    enc = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    fb = scriptlets.fake_body
    check(fb(enc({"t": "text/plain", "b": "héllo"})) == ("text/plain", "héllo".encode()), "literal body utf-8")
    check(fb(enc({"t": "application/json", "b": "{}"}), "HEAD") == ("application/json", b""), "HEAD empty")
    r = fb(enc({"t": "text/plain", "n": 1000}))
    check(r is not None and len(r[1]) == 1000 and r[1].isalnum(), "random length body")
    check(fb(enc({"t": "text/plain", "n": 500001})) is None, "length cap")
    check(fb(enc({"t": "text/plain", "n": True})) is None, "bool length rejected")
    check(fb(enc({"t": "text/html\r\nX-Evil: 1", "b": ""})) is None, "header injection in mime rejected")
    check(fb(enc({"t": "application/xml; charset=utf-8", "b": "<a/>"})) == ("application/xml; charset=utf-8", b"<a/>"),
          "mime with charset")
    check(fb("!!!notbase64") is None and fb("") is None and fb(enc([1, 2])) is None, "garbage -> None")
    check(fb(enc({"t": "text/plain", "b": "x"}) + "?q=1") == ("text/plain", b"x"), "query ignored")


NODE_HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const mk = new Function('return (' + src.replace(/^\s*\/\/.*$/mg, '') + ');');
const lib = mk();
const n = {
  apply: Reflect.apply, isArray: Array.isArray, keys: Object.keys, aSplice: Array.prototype.splice,
  JSON_parse: JSON.parse, JSON_stringify: JSON.stringify, RegExp: RegExp, reTest: RegExp.prototype.test,
  reExec: RegExp.prototype.exec, sSlice: String.prototype.slice, sTrim: String.prototype.trim,
  sStartsWith: String.prototype.startsWith, sEndsWith: String.prototype.endsWith, sIncludes: String.prototype.includes,
  sReplace: String.prototype.replace, sSplit: String.prototype.split, Set: Set, Map: Map, create: Object.create,
  Number: Number, String: String, aIndexOf: Array.prototype.indexOf, aJoin: Array.prototype.join,
};
const R = { n: n, apply: Reflect.apply, win: globalThis, now: () => 1234,
  str: v => typeof v === 'string' ? v : (v === null ? 'null' : (typeof v === 'object' || typeof v === 'function') ? '' : String(v)) };
const J = lib(R);
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = [];
for (const c of cases) {
  let res;
  try {
    const obj = JSON.parse(c.input);
    let changed;
    if (c.kind === 'prune') {
      const p = J.pruner(c.q, c.needle || '');
      if (!p) { out.push('INERT'); continue; }
      changed = p(obj);
    } else {
      const q = J.path(c.q, !!c.trusted);
      if (!q) { out.push('INERT'); continue; }
      changed = q.run(obj);
    }
    res = JSON.stringify(obj) + (changed ? '' : ' (unchanged)');
  } catch (e) { res = 'THROW ' + e; }
  out.push(res);
}
console.log(JSON.stringify(out));
"""

CASES = [
    # legacy json-prune paths (spec 02 14)
    ("prune", "ads", "", '{"ads":1,"k":2}', '{"k":2}'),
    ("prune", "playlist.[].adserver", "", '{"playlist":[{"adserver":1,"a":1},{"a":2}]}', '{"playlist":[{"a":1},{"a":2}]}'),
    ("prune", "[].playerResponse.adPlacements", "", '[{"playerResponse":{"adPlacements":[],"v":1}}]', '[{"playerResponse":{"v":1}}]'),
    ("prune", "entries.[-].command.reelWatchEndpoint.adClientParams.isAd", "",
     '{"entries":[{"command":{"reelWatchEndpoint":{"adClientParams":{"isAd":true}}}},{"command":{}}]}', '{"entries":[{"command":{}}]}'),
    ("prune", "pins.{-}.pin_promotion_id", "", '{"pins":{"a":{"pin_promotion_id":1},"b":{"x":1}}}', '{"pins":{"b":{"x":1}}}'),
    ("prune", "data.*.products.[-].sponsored_ad.ad_source", "",
     '{"data":{"m1":{"products":[{"sponsored_ad":{"ad_source":1}},{"id":2}]}}}', '{"data":{"m1":{"products":[{"id":2}]}}}'),
    ("prune", "*", "showTrkURL", '{"showTrkURL":1,"z":2}', '{}'),
    ("prune", "*", "showTrkURL", '{"z":2}', '{"z":2} (unchanged)'),
    ("prune", "a b.c", "x y", '{"a":1,"b":{"c":1},"x":0,"y":null}', '{"b":{},"x":0,"y":null}'),
    ("prune", "a", "x y", '{"a":1,"x":0}', '{"a":1,"x":0} (unchanged)'),
    ("prune", "list.0", "", '{"list":[1,2,3]}', '{"list":[2,3]}'),
    ("prune", "missing.deep.path", "", '{"a":1}', '{"a":1} (unchanged)'),
    ("prune", "", "", '{"a":1}', "INERT"),
    # JSONPath, legacy dialect (spec 02 15.1, 03b 9.1)
    ("path", "..searchResults.*[?.isAd==true]", "", '{"a":{"searchResults":[{"isAd":true},{"isAd":false}]}}',
     '{"a":{"searchResults":[{"isAd":false}]}}'),
    ("path", '.props[?.id=="freestar-adblock-recovery"].dangerouslySetInnerHTML', "",
     '{"props":{"id":"freestar-adblock-recovery","dangerouslySetInnerHTML":{"__html":"x"},"k":1}}',
     '{"props":{"id":"freestar-adblock-recovery","k":1}}'),
    ("path", '..node[?.*.__typename=="SponsoredData"]', "",
     '{"edges":[{"node":{"a":{"__typename":"SponsoredData"}}},{"node":{"a":{"__typename":"X"}}}]}',
     '{"edges":[{},{"node":{"a":{"__typename":"X"}}}]}'),
    ("path", "$./^(bannerUnderComments|bannerBottom)$/", "", '{"bannerUnderComments":1,"bannerBottom":2,"bannerTop":3}',
     '{"bannerTop":3}'),
    ("path", ".*[?.adId]", "", '[{"adId":1},{"id":2},{"adId":3}]', '[{"id":2}]'),
    ("path", '..[?..resource^="nc-ad"]', "", '{"w":[{"x":{"resource":"nc-ad-1"}},{"x":{"resource":"ok"}}]}', None),
    ("path", ".items.*[?.n>5]", "", '{"items":[{"n":3},{"n":7},{"n":"9"}]}', '{"items":[{"n":3},{"n":"9"}]}'),
    ("path", '.items.*[?.u=/^https?:\\/\\/ads\\./]', "", '{"items":[{"u":"https://ads.x"},{"u":"https://x"}]}',
     '{"items":[{"u":"https://x"}]}'),
    ("path", '.items.*[?!.keep]', "", '{"items":[{"keep":1},{"x":1}]}', '{"items":[{"keep":1}]}'),
    ("path", ".a=1", "", '{"a":0}', "INERT"),                                         # untrusted assignment
    ("path", ".a[", "", '{"a":0}', "INERT"),
    ("path", ".a=call([1])", "t", '{"a":0}', "INERT"),
    # trusted assignments
    ("path", '.features.*[?.slug=="adblock-detection"].enabled=false', "t",
     '{"features":[{"slug":"adblock-detection","enabled":true},{"slug":"x","enabled":true}]}',
     '{"features":[{"slug":"adblock-detection","enabled":false},{"slug":"x","enabled":true}]}'),
    ("path", "..allowAdblock=true", "t", '{"a":{"allowAdblock":false},"allowAdblock":0}', '{"a":{"allowAdblock":true},"allowAdblock":true}'),
    ("path", '[?.attestationRequest].context.client[?.clientName=="WEB"]+={"clientScreen":"CHANNEL"}', "t",
     '{"attestationRequest":1,"context":{"client":{"clientName":"WEB"}}}',
     '{"attestationRequest":1,"context":{"client":{"clientName":"WEB","clientScreen":"CHANNEL"}}}'),
    ("path", '.s=repl({"regex":"a+","replacement":"b"})', "t", '{"s":"xaaya"}', '{"s":"xbyb"}'),
    ("path", '.s=repl({"pattern":"ad","replacement":"-"})', "t", '{"s":"ad1ad2"}', '{"s":"-1-2"}'),
    ("path", '.lact="${now}"', "t", '{"lact":0}', '{"lact":"1234"}'),
    ("path", ".a.b=null", "t", '{"a":{"b":1}}', '{"a":{"b":null}}'),
    # v2 dialect
    ("path", "v2:$./^adv_/", "", '{"adv_a":1,"advb":2,"adv_c":3}', '{"advb":2}'),
    ("path", "v2:$.store.bicycle{0};$..book[?@.price<10]", "",
     '{"store":{"book":[{"price":8},{"price":12}]}}', '{"store":{"book":[{"price":12}]}}'),
    ("path", "v2:$.store.bicycle{0};$..book[?@.price<10]", "",
     '{"store":{"bicycle":{},"book":[{"price":8}]}}', '{"store":{"bicycle":{},"book":[{"price":8}]}} (unchanged)'),
    ("path", "v2:$.list[-1]", "", '{"list":[1,2,3]}', '{"list":[1,2]}'),
    ("path", "v2:$['a b']", "", '{"a b":1,"c":2}', '{"c":2}'),
    ("path", "v2:$..[?@.ad==true]", "", '{"x":[{"ad":true},{"ad":false}]}', '{"x":[{"ad":false}]}'),
]


def t_node():
    node = shutil.which("node")
    if not node:
        print("note: node not found, JS checks skipped")
        return
    d = tempfile.mkdtemp(prefix="luna-s1-")
    try:
        # 1) every SCRIPTLETS-1 scriptlet in one bundle parses
        js = scriptlets.build([(nm, ["x", "y"], True) for nm in sorted(MINE)], "x.com", sr="xq://l/t/")
        check(js is not None, "bundle with every SCRIPTLETS-1 scriptlet")
        for bad in ("eval(", "new Function", "console", "debugger", "innerHTML", "textContent ="):
            check(bad not in js.replace('"eval"', ""), "no %r in bundle" % bad)
        p = os.path.join(d, "b.js")
        with open(p, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([node, "--check", p], capture_output=True, text=True)
        check(r.returncode == 0, "node --check bundle", r.stderr[:400])
        # 2) the JSON engines
        lib = os.path.join(REPO, "adblock", "js", "scriptlets", "lib-json.js")
        cp = os.path.join(d, "cases.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump([{"kind": k, "q": q, "needle": nd, "trusted": nd == "t", "input": i} for k, q, nd, i, _ in CASES], f)
        hp = os.path.join(d, "h.js")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(NODE_HARNESS)
        r = subprocess.run([node, hp, lib, cp], capture_output=True, text=True)
        check(r.returncode == 0, "node harness ran", r.stderr[:400])
        got = json.loads(r.stdout) if r.returncode == 0 else []
        for (k, q, nd, i, exp), g in zip(CASES, got):
            if exp is None:
                check(isinstance(g, str) and not g.startswith("THROW") and "nc-ad" not in g, "%s %s" % (k, q), g)
            else:
                check(g == exp, "%s %r needle=%r" % (k, q, nd), g)
        check(len(got) == len(CASES), "all cases evaluated")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    t_names()
    t_fake_body()
    t_node()
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)))
    sys.exit(1 if FAILS else 0)
