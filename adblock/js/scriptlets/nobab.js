// @world: main
// nobab (bab-defuser, prevent-bab): BlockAdBlock, obfuscated eval loader. eval() of a string recognised as the
// BlockAdBlock payload returns undefined without running it, and its visible effects are undone (inline
// visibility on <body>, babasbm* message elements). String timers ending in ".bab_elementid?" run a no-op
// (the page still gets a real timer id). Spec 03c 14, 04 5.18.
function (R, ...args) {
  var n = R.n, win = R.win, doc = R.doc;
  var LOADER = ["ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", "String.fromCharCode",
    "DOMContentLoaded", "doScroll", "clientWidth"];
  var RE_ID = /blockadblock|babasbm|bab_elementid/i, RE_TIMER = /\.bab_elementid.$/;
  var styleGet = R.findDesc(win.HTMLElement.prototype, "style").desc.get;
  var removeProp = win.CSSStyleDeclaration.prototype.removeProperty;
  var gpv = win.CSSStyleDeclaration.prototype.getPropertyValue;
  function isBab(s) {
    if (typeof s !== "string" || s.length < 20) return false;
    if (R.apply(n.reTest, RE_ID, [s])) return true;
    if (R.includes(s, "babn") && R.includes(s, "getItem")) return true;
    for (var i = 0; i < LOADER.length; i++) if (!R.includes(s, LOADER[i])) return false;
    return R.includes(s, "sessionStorage") || R.includes(s, "localStorage") || R.includes(s, "Math.random");
  }
  function undo() {
    var b = R.apply(n.bodyGet, doc, []);
    if (b) {
      try {
        var st = R.apply(styleGet, b, []);
        if (R.apply(gpv, st, ["visibility"]) !== "") R.apply(removeProp, st, ["visibility"]);
      } catch (e) { /* ignore */ }
    }
    var l;
    try { l = R.toArray(R.apply(n.querySelectorAll, doc, ['[id^="babasbm"]'])); } catch (e) { return; }
    for (var i = 0; i < l.length; i++) { try { R.apply(n.remove, l[i], []); } catch (e) { /* ignore */ } }
  }
  var defused = false;
  function tidy() { undo(); R.later(undo, 500); }
  R.wrapMethod(win, "eval", function (t, th, a) {
    if (isBab(a[0])) {
      if (!defused) {
        defused = true;
        R.onReady(tidy, "interactive");
      }
      return undefined;
    }
    return R.apply(t, th, a);
  });
  var noop = R.anon(function () {});
  R.wrapMethod(win, "setTimeout", function (t, th, a) {
    if (typeof a[0] === "string" && R.apply(n.reTest, RE_TIMER, [a[0]])) {
      var b = R.slice(a, 0);
      b[0] = noop;
      return R.apply(t, th, b);
    }
    return R.apply(t, th, a);
  });
}
