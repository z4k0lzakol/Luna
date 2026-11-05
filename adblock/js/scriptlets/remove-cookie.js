// @world: main
// remove-cookie (cookie-remover): remove-cookie([needle]); vararg when (space-separated event names).
// needle is matched against cookie names (empty = all). Removal writes expired cookies for path {none, /} x
// domain {none, host, .host, .host-without-www}. Without "when": now and on pagehide/beforeunload; with "when":
// on each listed event (capture, passive), debounced 500 ms. Spec 03c 11.3.
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["when", "log", "debug"], 1);
  var n = R.n, win = R.win, doc = R.doc;
  var P = R.pattern(A.p[0], false);
  var host = "";
  try { host = R.str(win.location.hostname); } catch (e) { host = ""; }
  var domains = [""];
  if (host !== "") {
    R.push(domains, "; domain=" + host);
    R.push(domains, "; domain=." + host);
    if (R.startsWith(host, "www.")) R.push(domains, "; domain=." + R.slice(host, 4));
  }
  var EXP = "=; max-age=-1; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  function removeAll() {
    var all = "";
    try { all = R.str(R.apply(n.cookieGet, doc, [])); } catch (e) { return; }
    if (all === "") return;
    var parts = R.split(all, ";");
    for (var i = 0; i < parts.length; i++) {
      var p = R.trim(parts[i]);
      if (p === "") continue;
      var k = R.indexOf(p, "=");
      var nm = k === -1 ? p : R.slice(p, 0, k);
      var test = nm;
      try { test = n.decodeURIComponent(nm); } catch (e) { test = nm; }
      if (!P.test(test) && !P.test(nm)) continue;
      for (var d = 0; d < domains.length; d++) {
        try {
          R.apply(n.cookieSet, doc, [nm + EXP + domains[d]]);
          R.apply(n.cookieSet, doc, [nm + EXP + "; path=/" + domains[d]]);
        } catch (e) { /* ignore */ }
      }
    }
  }
  var when = A.x.when !== undefined ? R.trim(A.x.when) : "";
  if (when === "") {
    removeAll();
    var opts = { capture: true, passive: true };
    try {
      R.apply(n.addEventListener, win, ["pagehide", R.anon(function () { removeAll(); }), opts]);
      R.apply(n.addEventListener, win, ["beforeunload", R.anon(function () { removeAll(); }), opts]);
    } catch (e) { /* ignore */ }
    return;
  }
  var evs = R.split(when, " "), timer = 0;
  var deb = R.anon(function () {
    if (timer) return;
    timer = R.later(function () { timer = 0; removeAll(); }, 500);
  });
  for (var i = 0; i < evs.length; i++) {
    var ev = R.trim(evs[i]);
    if (ev === "") continue;
    try {
      R.apply(n.addEventListener, win, [ev, deb, { capture: true, passive: true }]);
      R.apply(n.addEventListener, doc, [ev, deb, { capture: true, passive: true }]);
    } catch (e) { /* ignore */ }
  }
}
