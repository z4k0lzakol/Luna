// @world: main
// remove-attr (ra): ra(names, [selector], [behaviour]); varargs quitAfter, runAt. names joined by "|".
// behaviour tokens: asap (now and again at DOMContentLoaded), stay (keep acting on DOM changes),
// complete (start at load); default start = DOMContentLoaded. Spec 03c 4.
// Internal form (used by remove-class): first argument {cls: true}.
function (R, ...args) {
  var cls = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    cls = args[0].cls === true;
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 3, ["quitAfter", "runAt", "log", "debug"], 1);
  var n = R.n, doc = R.doc;
  var raw = R.split(A.p[0], "|"), names = [];
  for (var i = 0; i < raw.length; i++) {
    var t = R.trim(raw[i]);
    if (t !== "") R.push(names, t);
  }
  if (!names.length) return;
  var sel = R.trim(A.p[1]);
  if (sel === "") {
    var parts = [];
    for (var j = 0; j < names.length; j++) {
      if (cls) R.push(parts, "." + (R.win.CSS && R.win.CSS.escape ? R.win.CSS.escape(names[j]) : names[j]));
      else R.push(parts, "[" + names[j] + "]");
    }
    sel = R.join(parts, ",");
  }
  try { R.apply(n.querySelectorAll, doc, [sel]); } catch (e) { return; }   // invalid selector -> inert
  var beh = " " + R.trim(A.p[2]) + " ";
  var asap = R.includes(beh, " asap "), stay = R.includes(beh, " stay "), complete = R.includes(beh, " complete ");
  if (A.x.runAt !== undefined) {
    var ra = A.x.runAt;
    if (ra === "complete" || ra === "idle" || ra === "3") complete = true;
    else if (ra === "loading" || ra === "1") asap = true;
  }
  var quitAfter = n.Number(A.x.quitAfter || "0");
  if (quitAfter !== quitAfter || quitAfter < 0) quitAfter = 0;
  var clRemove = R.win.DOMTokenList.prototype.remove, clContains = R.win.DOMTokenList.prototype.contains;
  var clGet = n.getOwnPropertyDescriptor(R.win.Element.prototype, "classList").get;
  var stopped = false, unobserve = null, queued = false;

  function pass() {
    queued = false;
    if (stopped) return;
    var list;
    try { list = R.toArray(R.apply(n.querySelectorAll, doc, [sel])); } catch (e) { return; }
    for (var k = 0; k < list.length; k++) {
      var el = list[k];
      for (var m = 0; m < names.length; m++) {
        try {
          if (cls) {   // remove() rewrites the class attribute even when absent -> would feed our own observer
            var tl = R.apply(clGet, el, []);
            if (R.apply(clContains, tl, [names[m]])) R.apply(clRemove, tl, [names[m]]);
          }
          else if (R.apply(n.hasAttribute, el, [names[m]])) R.apply(n.removeAttribute, el, [names[m]]);
        } catch (e) { /* ignore */ }
      }
    }
  }
  function queue() {
    if (queued || stopped) return;
    queued = true;
    R.apply(n.queueMicrotask, R.win, [pass]);
  }
  function stop() {
    stopped = true;
    if (unobserve) { unobserve(); unobserve = null; }
  }
  function start() {
    pass();
    if (stay && !unobserve && !stopped) {
      var opts = { childList: true, subtree: true, attributes: true, attributeFilter: cls ? ["class"] : names };
      unobserve = R.observe(doc, opts, queue);
    }
    if (quitAfter > 0) R.later(stop, quitAfter);
  }
  if (asap) {
    start();
    R.onReady(pass, "interactive");
  } else {
    R.onReady(start, complete ? "complete" : "interactive");
  }
}
