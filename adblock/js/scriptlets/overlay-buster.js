// @world: main
// overlay-buster: for 30 s after DOMContentLoaded, removes position:fixed elements with a z-index >= 10 that cover
// at least 90 % of the viewport, then restores scrolling on <html>/<body>. Mutation-driven (throttled, no
// polling). Spec 03a 6.7.
function (R, ...args) {
  var n = R.n, win = R.win, doc = R.doc;
  var efp = win.Document.prototype.elementsFromPoint;
  var gpv = win.CSSStyleDeclaration.prototype.getPropertyValue;
  var setProp = win.CSSStyleDeclaration.prototype.setProperty;
  var wD = R.findDesc(win, "innerWidth"), hD = R.findDesc(win, "innerHeight");
  var sD = R.findDesc(win.HTMLElement.prototype, "style");
  if (typeof efp !== "function" || !wD || !wD.desc.get || !hD || !hD.desc.get || !sD || !sD.desc.get) return;
  var wGet = wD.desc.get, hGet = hD.desc.get, styleGet = sD.desc.get;
  var stopObs = null, pending = false, over = false;
  function cs(el, p) {
    try { return R.apply(gpv, R.apply(n.getComputedStyle, win, [el]), [p]); } catch (e) { return ""; }
  }
  function unlock(el) {
    if (!el) return;
    var o = cs(el, "overflow-y");
    if (o !== "hidden" && o !== "clip") return;
    try { R.apply(setProp, R.apply(styleGet, el, []), ["overflow", "auto", "important"]); } catch (e) { /* ignore */ }
  }
  function pass() {
    pending = false;
    if (over) return;
    var w = R.apply(wGet, win, []), h = R.apply(hGet, win, []);
    if (!(w > 0 && h > 0)) return;
    var root = R.apply(n.documentElementGet, doc, []), body = R.apply(n.bodyGet, doc, []);
    var list;
    try { list = R.apply(efp, doc, [w / 2, h / 2]); } catch (e) { return; }
    var removed = false;
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el === root || el === body || R.nodeType(el) !== 1) continue;
      if (cs(el, "position") !== "fixed") continue;
      var z = R.n.Number(cs(el, "z-index"));
      if (!(z >= 10)) continue;
      var r;
      try { r = R.apply(n.getBoundingClientRect, el, []); } catch (e) { continue; }
      var x0 = r.left > 0 ? r.left : 0, y0 = r.top > 0 ? r.top : 0;
      var x1 = r.right < w ? r.right : w, y1 = r.bottom < h ? r.bottom : h;
      if (x1 <= x0 || y1 <= y0 || (x1 - x0) * (y1 - y0) < 0.9 * w * h) continue;
      try { R.apply(n.remove, el, []); removed = true; } catch (e) { /* ignore */ }
    }
    if (removed) { unlock(root); unlock(body); }
  }
  function schedule() {
    if (pending || over) return;
    pending = true;
    R.later(pass, 100);
  }
  function stop() {
    over = true;
    if (stopObs) stopObs();
  }
  R.onReady(function () {
    pass();
    stopObs = R.observe(doc, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] }, schedule);
    R.later(stop, 30000);
  }, "interactive");
}
