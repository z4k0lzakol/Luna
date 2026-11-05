// @world: main
// disable-newtab-links: no arguments. A capture-phase click listener on document cancels clicks on <a>/<area>
// elements that carry a target attribute (the link does nothing). Spec 03a 6.3.
function (R, ...args) {
  var n = R.n, doc = R.doc;
  var stopProp = R.win.Event.prototype.stopPropagation;
  var h = R.anon(function (ev) {
    var t;
    try { t = ev.target; } catch (e) { return; }
    var a = null;
    try {
      if (R.nodeType(t) === 3) t = R.parent(t);
      if (R.nodeType(t) === 1) a = R.apply(n.closest, t, ["a,area"]);
    } catch (e) { a = null; }
    if (!a) return;
    var tg = null;
    try { tg = R.apply(n.getAttribute, a, ["target"]); } catch (e) { return; }
    if (tg === null) return;
    try {
      R.apply(n.preventDefault, ev, []);
      R.apply(stopProp, ev, []);
    } catch (e) { /* ignore */ }
  });
  try { R.apply(n.addEventListener, doc, ["click", h, true]); } catch (e) { /* ignore */ }
}
