// @world: main
// multiup: (no arguments) - semantics BELIEVED (spec 03c 13): on multiup.* mirror pages each host button carries
// its target URL in a "link" attribute but submits a form that goes through intermediate ad pages. A click on
// such an element (button/a/input with an http(s) "link" attribute) opens that URL directly instead: in a new
// tab when the enclosing form/link targets one, else in the current tab.
function (R, ...args) {
  var n = R.n, win = R.win, doc = R.doc;
  var open = win.open, assign = n.location.assign;
  var RE = /^https?:\/\//i;
  function attr(el, name) {   // missing attribute -> "" (R.str(null) would give "null")
    var v = null;
    try { v = R.apply(n.getAttribute, el, [name]); } catch (e) { v = null; }
    return typeof v === "string" ? v : "";
  }
  var onClick = R.anon(function (ev) {
    var t = null, el = null;
    try { t = ev.target; } catch (e) { return; }
    if (R.nodeType(t) !== 1) return;
    try { el = R.apply(n.closest, t, ["button[link],a[link],input[link]"]); } catch (e) { el = null; }
    if (!el) return;
    var link = R.trim(attr(el, "link"));
    if (!R.apply(n.reTest, RE, [link])) return;
    R.apply(n.preventDefault, ev, []);
    R.apply(n.stopImmediatePropagation, ev, []);
    var host = null, tgt = "";
    try { host = R.apply(n.closest, el, ["form,a"]); } catch (e) { host = null; }
    if (host) tgt = R.lower(R.trim(attr(host, "target")));
    if (tgt === "" && R.nodeName(el) === "A") tgt = R.lower(R.trim(attr(el, "target")));
    try {
      if (tgt !== "" && tgt !== "_self" && tgt !== "_top" && tgt !== "_parent" && typeof open === "function") {
        R.apply(open, win, [link, "_blank", "noopener"]);
      } else {
        R.apply(assign, n.location, [link]);
      }
    } catch (e) { /* ignore */ }
  });
  R.apply(n.addEventListener, doc, ["click", onClick, true]);
}
