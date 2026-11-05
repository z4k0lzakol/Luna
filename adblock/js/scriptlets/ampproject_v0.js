// @world: main
// ampproject_v0: removes the AMP boilerplate that hides <body> for 8 s until the AMP runtime loads. Spec 03c 14,
// 04 5.11. At document start a MutationObserver removes style[amp-boilerplate] elements (and <noscript> fallbacks
// carrying it) as the parser inserts them; at DOMContentLoaded a final sweep runs, an inline `animation` on <body>
// is set to none and the observer stops.
function (R, ...args) {
  var n = R.n, win = R.win, doc = R.doc;
  var sD = R.findDesc(win.HTMLElement.prototype, "style");
  var gpv = win.CSSStyleDeclaration.prototype.getPropertyValue;
  var setProp = win.CSSStyleDeclaration.prototype.setProperty;
  if (!sD || !sD.desc.get) return;
  var styleGet = sD.desc.get;
  function sweep() {
    var l;
    try { l = R.apply(n.querySelectorAll, doc, ["style[amp-boilerplate], noscript"]); } catch (e) { return; }
    for (var i = 0; i < l.length; i++) {
      var el = l[i];
      if (R.nodeName(el) === "NOSCRIPT" && !R.includes(R.text(el), "amp-boilerplate")) continue;
      try { R.apply(n.remove, el, []); } catch (e) { /* ignore */ }
    }
  }
  var pending = false;
  var stop = R.observe(doc, { childList: true, subtree: true }, function (recs) {
    for (var i = 0; i < recs.length; i++) {
      var add = recs[i].addedNodes;
      for (var j = 0; j < add.length; j++) {
        var nn = R.nodeName(add[j]);
        if (nn === "STYLE" || nn === "NOSCRIPT") { pending = true; break; }
      }
      if (pending) break;
    }
    if (pending) { pending = false; sweep(); }
  });
  R.onReady(function () {
    stop();
    sweep();
    var b = R.apply(n.bodyGet, doc, []);
    if (!b) return;
    try {
      var st = R.apply(styleGet, b, []);
      if (R.apply(gpv, st, ["animation"]) !== "" || R.apply(gpv, st, ["animation-name"]) !== "") {
        R.apply(setProp, st, ["animation", "none"]);
      }
    } catch (e) { /* ignore */ }
  }, "interactive");
}
