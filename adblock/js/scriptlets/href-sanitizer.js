// @world: main
// href-sanitizer: href-sanitizer(selector, [source]). Default source: the link's text (must be an https: URL).
// Otherwise space-separated steps: [attr] ?name &i # /re/ +https -base64 -safebase64 -uricomponent -blocked.
// The result must be an absolute http(s) URL -> written to href. Runs at DOM ready and on DOM mutations.
// Spec 03c 9.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 2);
  var n = R.n, win = R.win, doc = R.doc;
  var sel = R.trim(A.p[0]), source = R.trim(A.p[1]);
  if (sel === "") return;
  try { R.apply(n.querySelectorAll, doc, [sel]); } catch (e) { return; }
  var URLc = n.URL;
  var hrefGet = n.getOwnPropertyDescriptor(URLc.prototype, "href").get;
  var protoGet = n.getOwnPropertyDescriptor(URLc.prototype, "protocol").get;
  var hashGet = n.getOwnPropertyDescriptor(URLc.prototype, "hash").get;
  var searchGet = n.getOwnPropertyDescriptor(URLc.prototype, "search").get;
  var USP = n.URLSearchParams, uspGet = USP.prototype.get, uspKeys = USP.prototype.keys;
  var itNext = null;
  try { itNext = R.apply(uspKeys, new USP(""), []).next; } catch (e) { itNext = null; }
  // steps: split on spaces, but keep /regex/ steps that contain spaces together
  var steps = [];
  if (source !== "") {
    var re = /\/(?:\\.|[^\/\\])+\/[a-z]*|\S+/g, m;
    while ((m = R.apply(n.reExec, re, [source])) !== null) R.push(steps, m[0]);
  }
  function parse(u) {
    try { return new URLc(u); } catch (e) { return null; }
  }
  function absURL(s) {   // -> absolute http(s) href or ""
    var u = parse(s);
    if (!u) return "";
    var pr = R.apply(protoGet, u, []);
    if (pr !== "http:" && pr !== "https:") return "";
    return R.apply(hrefGet, u, []);
  }
  function qsOf(s) {
    var u = parse(s), q;
    if (u) q = R.apply(searchGet, u, []);
    else {
      var k = R.indexOf(s, "?");
      if (k === -1) return null;
      q = R.slice(s, k);
      var h = R.indexOf(q, "#");
      if (h !== -1) q = R.slice(q, 0, h);
    }
    try { return new USP(q); } catch (e) { return null; }
  }
  function b64(s, safe) {
    var t = s;
    if (safe) t = R.sreplace(R.sreplace(t, /-/g, "+"), /_/g, "/");
    t = R.sreplace(t, /\s+/g, "");
    while (t.length % 4) t += "=";
    var bin = R.apply(n.atob, win, [t]);
    // UTF-8 decode when possible
    try {
      var bytes = new win.Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = R.apply(n.sCharCodeAt, bin, [i]);
      return R.apply(n.TextDecoder.prototype.decode, new n.TextDecoder("utf-8", { fatal: true }), [bytes]);
    } catch (e) { return bin; }
  }
  function runStep(cur, st, el) {   // -> string or null (failed)
    var c0 = st.charAt(0);
    if (c0 === "[" && st.charAt(st.length - 1) === "]") {
      var v = R.apply(n.getAttribute, el, [R.slice(st, 1, -1)]);
      return v === null ? null : v;
    }
    if (c0 === "?") {
      var names = R.split(R.slice(st, 1), "?"), s = cur;
      for (var i = 0; i < names.length; i++) {
        if (names[i] === "") return null;
        var q = qsOf(s);
        if (!q) return null;
        var r = R.apply(uspGet, q, [names[i]]);
        if (r === null) return null;
        s = r;
      }
      return s;
    }
    if (c0 === "&") {
      var idx = n.Number(R.slice(st, 1));
      if (!(idx >= 1)) return null;
      var q2 = qsOf(cur);
      if (!q2) return null;
      var it = R.apply(uspKeys, q2, []);
      if (!itNext) itNext = it.next;
      var k = 0, rr;
      while (!(rr = R.apply(itNext, it, [])).done) { k++; if (k === idx) return rr.value; }
      return null;
    }
    if (st === "#") {
      var u = parse(cur);
      var h = u ? R.apply(hashGet, u, []) : (R.indexOf(cur, "#") !== -1 ? R.slice(cur, R.indexOf(cur, "#")) : "");
      return h === "" ? null : R.slice(h, 1);
    }
    if (c0 === "/") {
      var P = R.pattern(st, false);
      if (P.kind !== "regex") return null;
      P.re.lastIndex = 0;
      var mm = R.apply(n.reExec, P.re, [cur]);
      if (!mm) return null;
      return mm[1] !== undefined ? mm[1] : mm[0];
    }
    if (st === "+https") {
      if (R.apply(n.reTest, /^https:\/\//i, [cur])) return cur;
      if (R.apply(n.reTest, /^http:\/\//i, [cur])) return "https://" + R.slice(cur, 7);
      if (R.startsWith(cur, "//")) return "https:" + cur;
      return "https://" + cur;
    }
    if (st === "-base64" || st === "-safebase64") {
      try { return b64(cur, st === "-safebase64"); } catch (e) { return null; }
    }
    if (st === "-uricomponent") {
      try { return n.decodeURIComponent(cur); } catch (e) { return null; }
    }
    if (st === "-blocked") return cur;
    return null;
  }
  function fix(el) {
    if (R.nodeName(el) !== "A" && R.nodeName(el) !== "AREA") return;
    var href = R.apply(n.getAttribute, el, ["href"]);
    if (href === null) return;
    var out;
    if (!steps.length) {
      out = R.trim(R.text(el));
      if (!R.apply(n.reTest, /^https:\/\/\S+$/, [out])) return;
    } else {
      out = href;
      for (var i = 0; i < steps.length; i++) {
        out = runStep(out, steps[i], el);
        if (out === null || typeof out !== "string") return;
      }
    }
    out = absURL(R.trim(out));
    if (out === "" || out === href) return;
    R.apply(n.setAttribute, el, ["href", out]);
  }
  var queued = false;
  function pass() {
    queued = false;
    var list;
    try { list = R.toArray(R.apply(n.querySelectorAll, doc, [sel])); } catch (e) { return; }
    for (var i = 0; i < list.length; i++) {
      try { fix(list[i]); } catch (e) { /* ignore */ }
    }
  }
  R.onReady(function () {
    pass();
    R.observe(doc, { childList: true, subtree: true, attributes: true, attributeFilter: ["href"] }, function () {
      if (queued) return;
      queued = true;
      R.apply(n.queueMicrotask, win, [pass]);
    });
  }, "interactive");
}
