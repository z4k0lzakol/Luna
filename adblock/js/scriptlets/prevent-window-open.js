// @world: main
// prevent-window-open (nowoif, no-window-open-if, window.open-defuser): nowoif([needle], [decoySec], [decoyType]).
// needle (negatable) is matched against all arguments joined with " "; empty = every call. Matching calls
// return null, or a hidden about:blank decoy window removed after decoySec ("obj" = <object> decoy), or with
// decoyType "blank" open about:blank instead. Spec 03a 6.1.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["log", "debug"], 1);
  var needle = A.p[0];
  if (needle === "debug") return;
  var P = R.pattern(needle, true);
  var secs = R.n.Number(R.trim(A.p[1]) || "0");
  if (secs !== secs || secs < 0) secs = 0;
  secs = R.apply(R.n.Math_floor, R.win.Math, [secs]);
  var dtype = R.trim(A.p[2]);
  var n = R.n, win = R.win, doc = R.doc;
  var hrefGet = n.getOwnPropertyDescriptor(n.URL.prototype, "href").get;
  function argText(v) {
    if (v !== null && typeof v === "object") {
      try { if (v instanceof n.URL) return R.apply(hrefGet, v, []); }
      catch (e) { return ""; }
      return "";
    }
    return R.str(v);
  }
  function decoy() {
    // "obj" decoys would need <object data=...>, a Trusted Types sink: always use a hidden iframe instead
    var isObj = false;
    var el = R.apply(n.createElement, doc, [isObj ? "object" : "iframe"]);
    R.apply(n.setAttribute, el, [isObj ? "data" : "src", "about:blank"]);
    R.apply(n.setAttribute, el, ["style",
      "position:fixed!important;top:-9999px!important;left:-9999px!important;width:1px!important;height:1px!important;visibility:hidden!important"]);
    var root = R.apply(n.documentElementGet, doc, []);
    if (!root) return null;
    R.apply(n.appendChild, root, [el]);
    var w = null;
    try { w = R.apply(isObj ? n.objectContentWindowGet : n.iframeContentWindowGet, el, []); } catch (e) { w = null; }
    if (w) { try { R.adopt(w); } catch (e) { /* ignore */ } }
    R.later(function () { R.apply(n.remove, el, []); }, secs * 1000);
    return w;
  }
  R.wrapMethod(win, "open", function (t, th, a) {
    var parts = [];
    for (var i = 0; i < a.length; i++) parts[i] = argText(a[i]);
    if (!P.test(R.join(parts, " "))) return R.apply(t, th, a);
    if (dtype === "blank") {
      var b = R.slice(a, 0);
      b[0] = "about:blank";
      return R.apply(t, th, b);
    }
    if (secs > 0) return decoy();
    return null;
  });
}
