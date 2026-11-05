// @world: main
// prevent-refresh (refresh-defuser): prevent-refresh([delaySec]). Spec 03a 6.4.
// Finds <meta http-equiv="refresh"> (as soon as the parser inserts it, else at DOM ready) and cancels the
// refresh navigation through the Navigation API: a navigate event that is not user-initiated, cancelable,
// of type replace/reload and heading to the meta's target URL gets preventDefault() (verified in QtWebEngine:
// window.stop() does not cancel an already scheduled refresh, the navigate event does). With an argument and no
// meta (HTTP "Refresh:" header) the first such navigation within 1.5 s of load + delaySec is cancelled.
// Fallback without the Navigation API: window.stop() shortly before the refresh fires.
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["log", "debug"], 1);
  var n = R.n, win = R.win, doc = R.doc;
  var arg = R.trim(A.p[0]);
  var argDelay = arg === "" ? NaN : n.Number(arg);
  if (argDelay !== argDelay || argDelay < 0) argDelay = NaN;
  var SEL = 'meta[http-equiv="refresh" i]';
  var nav = null;
  try { nav = win.navigation || null; } catch (e) { nav = null; }
  var NE = win.NavigateEvent, NDE = win.NavigationDestination;
  var g = function (C, p) { var d = C && n.getOwnPropertyDescriptor(C.prototype, p); return d && d.get; };
  var neType = g(NE, "navigationType"), neCancel = g(win.Event, "cancelable"), neUser = g(NE, "userInitiated");
  var neHash = g(NE, "hashChange"), neDest = g(NE, "destination"), ndURL = g(NDE, "url");
  var useNav = !!(nav && neType && neCancel && neUser && neDest && ndURL);
  var stopFn = win.stop;
  var URLc = n.URL, hrefGet = n.getOwnPropertyDescriptor(URLc.prototype, "href").get;
  var target = null, found = false, loadAt = -1, armed = false, unobserve = null;

  function docURL() {
    try { return R.str(win.location.href); } catch (e) { return ""; }
  }
  function abs(u) {
    try { return R.apply(hrefGet, new URLc(u, docURL()), []); } catch (e) { return null; }
  }
  function strip(u) { var k = R.indexOf(u, "#"); return k === -1 ? u : R.slice(u, 0, k); }
  function parseMeta(meta) {   // -> {delay, url}
    var c = "";
    try { c = R.str(R.apply(n.getAttribute, meta, ["content"])); } catch (e) { c = ""; }
    var m = R.apply(n.reExec, /^\s*(\d+(?:\.\d*)?)?\s*(?:[;,]\s*(?:url\s*=\s*)?([\s\S]*))?$/i, [c]);
    var d = m && m[1] !== undefined ? n.Number(m[1]) : 0;
    var u = m && m[2] !== undefined ? R.trim(m[2]) : "";
    if (u.length >= 2 && (u.charAt(0) === "'" || u.charAt(0) === '"') && u.charAt(u.length - 1) === u.charAt(0)) {
      u = R.slice(u, 1, -1);
    }
    return { delay: d, url: u === "" ? docURL() : u };
  }
  function onNavigate(ev) {
    try {
      if (R.apply(neUser, ev, []) || !R.apply(neCancel, ev, [])) return;
      if (neHash && R.apply(neHash, ev, [])) return;
      var t = R.apply(neType, ev, []);
      if (t !== "replace" && t !== "reload") return;
      var dest = R.str(R.apply(ndURL, R.apply(neDest, ev, []), []));
      if (target !== null) {
        if (strip(dest) !== strip(target)) return;
      } else {
        if (!armed || loadAt < 0) return;
        var dt = R.now() - loadAt - argDelay * 1000;
        if (dt < -1500 || dt > 1500) return;
        armed = false;
      }
      R.apply(n.preventDefault, ev, []);
    } catch (e) { /* ignore */ }
  }
  var listening = false;
  function listen() {
    if (listening || !useNav) return;
    listening = true;
    try { R.apply(n.addEventListener, nav, ["navigate", R.anon(function (ev) { onNavigate(ev); })]); } catch (e) { /* ignore */ }
  }
  function handle(meta) {
    if (found) return;
    found = true;
    if (unobserve) { unobserve(); unobserve = null; }
    var pm = parseMeta(meta);
    target = abs(pm.url);
    if (useNav && target !== null) { listen(); return; }
    // fallback: stop loading just before the refresh would fire
    if (typeof stopFn !== "function") return;
    var d = argDelay === argDelay ? argDelay : pm.delay;
    var ms = d * 1000 - 50;
    var stop = function () { try { R.apply(stopFn, win, []); } catch (e) { /* ignore */ } };
    if (ms <= 0) stop();
    else R.later(stop, ms);
  }
  function isMeta(nd) {
    try { return R.nodeType(nd) === 1 && R.apply(n.matches, nd, [SEL]); } catch (e) { return false; }
  }
  unobserve = R.observe(doc, { childList: true, subtree: true }, function (recs) {
    for (var i = 0; i < recs.length && !found; i++) {
      var add = recs[i].addedNodes;
      for (var j = 0; j < add.length && !found; j++) {
        var nd = add[j];
        if (isMeta(nd)) { handle(nd); break; }
        if (R.nodeType(nd) === 1) {
          var inner = null;
          try { inner = R.apply(n.elQuerySelector, nd, [SEL]); } catch (e) { inner = null; }
          if (inner) handle(inner);
        }
      }
    }
  });
  R.onReady(function () {
    if (unobserve) { unobserve(); unobserve = null; }
    if (found) return;
    var meta = null;
    try { meta = R.apply(n.querySelector, doc, [SEL]); } catch (e) { meta = null; }
    if (meta) { handle(meta); return; }
    if (argDelay === argDelay && useNav) {   // header refresh: arm around load + delay
      armed = true;
      listen();
      R.onReady(function () { loadAt = R.now(); }, "complete");
    }
  }, "interactive");
}
