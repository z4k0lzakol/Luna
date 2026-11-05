// @world: main
// abort-current-script (acs, abort-current-inline-script, acis): acs(chain, [needle], [srcNeedle]).
// Aborts the currently executing classic <script> when it reads/writes chain and its text (and src) match.
// Spec 03a 2.3. Missing intermediate objects: the first missing segment is trapped.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["debug", "log"], 1);
  var chain = A.p[0];
  if (chain === "") return;
  var n = R.n, doc = R.doc, msg = R.abortMsg(chain);
  var needle = R.pattern(A.p[1]);
  var srcN = A.p[2] !== "" ? R.pattern(A.p[2]) : null;
  var texts = new n.WeakMap();
  var wmGet = n.WeakMap.prototype.get, wmSet = n.WeakMap.prototype.set;
  function decodeData(src) {
    var i = R.indexOf(src, ",");
    if (i < 0) return "";
    var meta = R.slice(src, 5, i), body = R.slice(src, i + 1);
    try {
      if (R.endsWith(meta, ";base64")) return R.apply(n.atob, R.win, [body]);
      return R.apply(n.decodeURIComponent, R.win, [body]);
    } catch (e) { return ""; }
  }
  function srcOf(s) { try { return R.apply(n.scriptSrcGet, s, []) || ""; } catch (e) { return ""; } }
  function textOf(s) {
    var t = R.apply(wmGet, texts, [s]);
    if (t !== undefined) return t;
    t = R.text(s);
    if (R.trim(t) === "") {
      var src = srcOf(s);
      t = R.startsWith(src, "data:") ? decodeData(src) : "";
    }
    R.apply(wmSet, texts, [s, t]);
    return t;
  }
  var busy = false;
  function check(fn) {
    if (busy) return;
    var s;
    try { s = R.apply(n.currentScriptGet, doc, []); } catch (e) { return; }
    if (!s || !(s instanceof n.HTMLScriptElement)) return;
    busy = true;
    var hit = false;
    try {
      hit = (!srcN || srcN.test(srcOf(s))) && (needle.kind === "all" || needle.test(textOf(s)));
    } finally { busy = false; }
    if (hit) R.abort(msg, fn);
  }
  R.trap(R.win, chain, {
    defer: "none",
    get: function (st, rcv) { check(st.fnGet); return R.passGet(st, rcv); },
    set: function (st, v, rcv) { check(st.fnSet); R.passSet(st, v, rcv); }
  });
}
