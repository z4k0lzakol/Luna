"""Pure-Python tests for adblock/scriptlet_names.py and adblock/scriptlets.py (no Qt).
Run: python -I tests/adblock/test_scriptlets.py
"""
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

FAILS = []
COUNT = [0]


def check(cond, label):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
        print("FAIL:", label)


def t_names():
    c = names.canonical
    check(c("set") == "set-constant", "alias set")
    check(c("set.js") == "set-constant", ".js suffix")
    check(c("set-constant.js") == "set-constant", "canonical .js")
    check(c("ubo-nostif.js") == "prevent-setTimeout", "ubo- prefix")
    check(c("nano-sib") == "adjust-setInterval", "nano-sib")
    check(c("window.open-defuser") == "prevent-window-open", "dotted alias")
    check(c("fuckadblock.js-3.2.0") == "nofab", "fab alias")
    check(c("nope-nope") is None, "unknown -> None")
    check(c("") is None and c(None) is None, "empty")
    check("rpnt" in names.TRUSTED_ONLY and "trusted-set" in names.TRUSTED_ONLY, "trusted aliases")
    check("trusted-set-cookie" in names.TRUSTED_ONLY, "trusted canonical")
    check("set-constant" not in names.TRUSTED_ONLY, "set not trusted")
    check(names.is_trusted_only("replace-node-text"), "is_trusted_only alias")
    for a, cn in names.ALIASES.items():
        check(cn in names.KNOWN, "alias target known: " + a)
        check(a not in names.KNOWN, "alias is not canonical: " + a)
    check(names.SUPPORTED <= names.KNOWN, "SUPPORTED subset of KNOWN")
    avail = scriptlets.available()
    check(names.SUPPORTED <= avail, "every SUPPORTED name has a file: %s" % sorted(names.SUPPORTED - avail))
    rt = {"set-constant", "abort-on-property-read", "abort-on-property-write", "abort-current-script",
          "abort-on-stack-trace", "prevent-setTimeout", "prevent-setInterval", "adjust-setTimeout",
          "adjust-setInterval", "addEventListener-defuser", "prevent-window-open", "remove-node-text"}
    check(rt <= names.SUPPORTED, "RUNTIME block complete")


def t_build():
    b = scriptlets.build
    check(b([], "x.com") is None, "empty -> None")
    check(b([("nope", [], True)], "x.com") is None, "unknown -> None")
    check(b([("rpnt", ["script", "x"], False)], "x.com") is None, "trusted-only from untrusted dropped")
    js = b([("set", ["a", "true"], False), ("set-constant", ["a", "true"], True), ("aopr", ["b"], False)],
           "x.com", sr="xabc://l/tok/")
    check(js is not None, "build ok")
    check(js.count('(R,"a","true")') == 1, "dedupe across aliases")
    check('"xabc://l/tok/"' in js, "SR embedded")
    check(scriptlets.SECRET in js, "secret embedded")
    check("sourceURL" not in js, "no sourceURL")
    check("console" not in js, "no console in bundle")
    for bad in ("eval(", "new Function", "Function(", "debugger"):
        check(bad not in js, "no %s in bundle" % bad)
    # arguments are JSON string literals, never spliced code
    evil = '");window.pwned=1;(" </script>'
    js2 = b([("set", [evil, "true"], False)], "x.com")
    check(json.dumps(evil, ensure_ascii=True) in js2, "arg JSON-encoded")
    check("window.pwned=1;(\"" not in js2.replace(json.dumps(evil, ensure_ascii=True), ""), "no raw splice")
    # deps: prevent-setInterval pulls prevent-setTimeout once
    js3 = b([("nosiif", ["x"], False), ("nostif", ["y"], False)], "x.com")
    import re
    check(len(re.findall(r"(?m)^var a\d+=", js3)) == 2, "deps included once")
    check('"prevent-setTimeout":a0' in js3, "deps map")
    # syntax check of a bundle with every RUNTIME scriptlet (node, if available)
    allr = [(n, ["x"], True) for n in sorted(names.SUPPORTED)]
    js4 = b(allr, "x.com")
    check(js4 is not None and js4.startswith("(function(){") and js4.endswith("})();"), "bundle shape")
    node = shutil.which("node")
    if node:
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "b.js")
            with open(p, "w", encoding="utf-8") as f:
                f.write(js4)
            r = subprocess.run([node, "--check", p], capture_output=True, text=True)
            check(r.returncode == 0, "node --check: " + r.stderr[:300])
        finally:
            shutil.rmtree(d, ignore_errors=True)
    else:
        print("note: node not found, syntax check skipped")
    print("bundle size with all RUNTIME scriptlets: %d bytes" % len(js4))


if __name__ == "__main__":
    t_names()
    t_build()
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)))
    sys.exit(1 if FAILS else 0)
