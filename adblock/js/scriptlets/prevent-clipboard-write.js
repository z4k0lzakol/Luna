// @world: main
// prevent-clipboard-write: (needle); varargs domAlert <message>, excludeMatches <pattern>. Spec 03a 7.5.
// Anti-"ClickFix": text written to the clipboard (navigator.clipboard.writeText/write, clipboardData.setData in
// copy handlers, plain copy of a selection) that matches needle and not excludeMatches is not written; the
// promise resolves normally. With domAlert a Polish in-page notice is shown (the list's own message is not
// used: it names another product).
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["domAlert", "excludeMatches", "log", "debug"], 1);
  var needle = A.p[0];
  if (needle === "") return;
  var n = R.n, win = R.win, doc = R.doc;
  var P = R.pattern(needle, false);
  var ex = A.x.excludeMatches !== undefined ? A.x.excludeMatches : "";
  var EX = ex !== "" ? R.pattern(ex, false) : null;
  var notice = A.x.domAlert !== undefined;
  var promiseAll = n.Promise.all;
  function bad(t) {
    return typeof t === "string" && t !== "" && P.test(t) && !(EX && EX.test(t));
  }
  var styleGet = R.findDesc(win.HTMLElement.prototype, "style").desc.get;
  var setProp = win.CSSStyleDeclaration.prototype.setProperty;
  var attachShadow = win.Element.prototype.attachShadow;
  var lastNotice = 0;
  function notify(text) {
    if (!notice) return;
    var now = R.now();
    if (now - lastNotice < 2000) return;
    lastNotice = now;
    try {
      var host = R.apply(n.createElement, doc, ["div"]);
      var root = R.apply(attachShadow, host, [{ mode: "closed" }]);
      var box = R.apply(n.createElement, doc, ["div"]);
      var snippet = R.slice(text, 0, 300) + (text.length > 300 ? "…" : "");
      R.apply(n.textContentSet, box, ["Luna zablokowała podejrzane kopiowanie do schowka (możliwy atak „ClickFix”). " +
        "Nie wklejaj tego tekstu w terminalu ani w oknie Uruchom:\n\n" + snippet]);
      var hs = R.apply(styleGet, host, []), bs = R.apply(styleGet, box, []);
      var hp = [["all", "initial"], ["position", "fixed"], ["top", "12px"], ["left", "12px"], ["right", "12px"],
        ["z-index", "2147483647"], ["display", "block"]];
      var bp = [["display", "block"], ["max-width", "720px"], ["margin", "0 auto"], ["padding", "14px 18px"],
        ["background", "#8b1a1a"], ["color", "#fff"], ["font", "14px/1.45 system-ui, sans-serif"],
        ["border-radius", "10px"], ["box-shadow", "0 6px 24px rgba(0,0,0,.35)"], ["white-space", "pre-wrap"],
        ["word-break", "break-word"], ["cursor", "pointer"], ["text-align", "left"]];
      var i;
      for (i = 0; i < hp.length; i++) R.apply(setProp, hs, [hp[i][0], hp[i][1], "important"]);
      for (i = 0; i < bp.length; i++) R.apply(setProp, bs, [bp[i][0], bp[i][1], "important"]);
      R.apply(n.appendChild, root, [box]);
      var drop = R.anon(function () { try { R.apply(n.remove, host, []); } catch (e) { /* ignore */ } });
      R.apply(n.addEventListener, box, ["click", drop]);
      var parent = R.apply(n.bodyGet, doc, []) || R.apply(n.documentElementGet, doc, []);
      if (!parent) return;
      R.apply(n.appendChild, parent, [host]);
      R.later(drop, 15000);
    } catch (e) { /* ignore */ }
  }
  var resolved = function () { return R.apply(n.promiseResolve, n.Promise, [undefined]); };
  var CB = win.Clipboard;
  if (typeof CB === "function") {
    R.wrapMethod(CB.prototype, "writeText", function (t, th, a) {
      var s = R.str(a[0]);
      if (bad(s)) { notify(s); return resolved(); }
      return R.apply(t, th, a);
    });
    var CI = win.ClipboardItem;
    var typesD = typeof CI === "function" ? R.findDesc(CI.prototype, "types") : null;
    var getType = typeof CI === "function" ? CI.prototype.getType : null;
    var blobText = win.Blob.prototype.text;
    R.wrapMethod(CB.prototype, "write", function (t, th, a) {
      var items = a[0];
      if (!typesD || !typesD.desc.get || typeof getType !== "function" || !n.isArray(items)) return R.apply(t, th, a);
      var ps = [];
      for (var i = 0; i < items.length; i++) {
        try {
          var ty = R.apply(typesD.desc.get, items[i], []);
          if (R.apply(n.aIndexOf, ty, ["text/plain"]) === -1) continue;
          var p = R.apply(getType, items[i], ["text/plain"]);
          ps[ps.length] = R.apply(n.promiseThen, p, [function (b) { return R.apply(blobText, b, []); }]);
        } catch (e) { /* ignore */ }
      }
      if (!ps.length) return R.apply(t, th, a);
      var all = R.apply(promiseAll, n.Promise, [ps]);
      return R.apply(n.promiseThen, all, [function (texts) {
        for (var k = 0; k < texts.length; k++) {
          if (bad(texts[k])) { notify(texts[k]); return undefined; }
        }
        return R.apply(t, th, a);
      }, function () { return R.apply(t, th, a); }]);
    });
  }
  var DT = win.DataTransfer;
  if (typeof DT === "function") {
    R.wrapMethod(DT.prototype, "setData", function (t, th, a) {
      var fmt = R.lower(R.trim(R.str(a[0])));
      if ((fmt === "text/plain" || fmt === "text" || fmt === "text/unicode") && bad(R.str(a[1]))) {
        notify(R.str(a[1]));
        return undefined;
      }
      return R.apply(t, th, a);
    });
  }
  var getSel = win.getSelection, selToString = win.Selection && win.Selection.prototype.toString;
  var activeD = R.findDesc(win.Document.prototype, "activeElement");
  var TA = win.HTMLTextAreaElement, IN = win.HTMLInputElement;
  function fieldText(el) {
    var proto = el instanceof TA ? TA.prototype : el instanceof IN ? IN.prototype : null;
    if (!proto) return "";
    try {
      var v = R.apply(R.findDesc(proto, "value").desc.get, el, []);
      var s = R.apply(R.findDesc(proto, "selectionStart").desc.get, el, []);
      var e = R.apply(R.findDesc(proto, "selectionEnd").desc.get, el, []);
      return typeof s === "number" && typeof e === "number" && e > s ? R.slice(v, s, e) : "";
    } catch (x) { return ""; }
  }
  var onCopy = R.anon(function (ev) {
    var text = "";
    try { text = R.apply(selToString, R.apply(getSel, win, []), []); } catch (e) { text = ""; }
    if (text === "" && activeD && activeD.desc.get) {
      try { var ae = R.apply(activeD.desc.get, doc, []); if (ae) text = fieldText(ae); } catch (e) { text = ""; }
    }
    if (bad(text)) { notify(text); R.apply(n.preventDefault, ev, []); }
  });
  if (typeof getSel === "function" && typeof selToString === "function") {
    try { R.apply(n.addEventListener, win, ["copy", onCopy, true]); } catch (e) { /* ignore */ }
  }
}
