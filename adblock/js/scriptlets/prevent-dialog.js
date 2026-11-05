// @world: main
// prevent-dialog: ([extraSelector]) - extraSelector is appended to "dialog" (e.g. "[open]", ".cookie-modal").
// Open matching <dialog> elements are closed at DOM ready and whenever they appear or get opened; show() /
// showModal() on a matching dialog do nothing. Spec 03a 6.8.
function (R, ...args) {
  var n = R.n, win = R.win, doc = R.doc;
  var HD = win.HTMLDialogElement;
  if (typeof HD !== "function") return;
  var sel = "dialog" + R.trim(R.str(args[0]));
  try { R.apply(n.querySelector, doc, [sel]); } catch (e) { return; }
  var oD = R.findDesc(HD.prototype, "open");
  var close = HD.prototype.close;
  var gebtn = win.Document.prototype.getElementsByTagName;
  var lenD = R.findDesc(win.HTMLCollection.prototype, "length");
  if (!oD || !oD.desc.get || typeof close !== "function" || !lenD || !lenD.desc.get) return;
  var openGet = oD.desc.get, lenGet = lenD.desc.get;
  var all = R.apply(gebtn, doc, ["dialog"]);
  function isMatch(el) {
    try { return R.apply(n.matches, el, [sel]); } catch (e) { return false; }
  }
  function sweep() {
    if (R.apply(lenGet, all, []) === 0) return;
    var l;
    try { l = R.apply(n.querySelectorAll, doc, [sel]); } catch (e) { return; }
    for (var i = 0; i < l.length; i++) {
      try { if (R.apply(openGet, l[i], [])) R.apply(close, l[i], []); } catch (e) { /* ignore */ }
    }
  }
  var noShow = function (t, th, a) {
    if (isMatch(th)) return undefined;
    return R.apply(t, th, a);
  };
  R.wrapMethod(HD.prototype, "showModal", noShow);
  R.wrapMethod(HD.prototype, "show", noShow);
  R.observe(doc, { childList: true, subtree: true, attributes: true, attributeFilter: ["open"] }, sweep);
  R.onReady(sweep, "interactive");
}
