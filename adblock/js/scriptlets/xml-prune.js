// @deps: lib-net
// @world: main
// xml-prune: (selector, [checkSelector], [urlNeedle]); varargs logdoc, log.
// fetch and XHR responses whose URL matches urlNeedle (pattern, "" = all) and whose text starts with "<" are parsed
// as XML (pristine DOMParser); unless checkSelector is set and matches nothing, the elements selected by selector
// (CSS, or xpath(EXPR) selecting elements or attributes) are removed and the document re-serialised (the original
// XML declaration is kept). XHR responseType "document" is pruned in place. Spec 03b 10.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["logdoc", "log", "debug"], 1);
  var sel = R.trim(A.p[0]), chk = R.trim(A.p[1]);
  if (sel === "") return;
  var N = R.deps["lib-net"](R), n = R.n, win = R.win;
  var UP = R.pattern(A.p[2], false);
  var DocP = win.Document.prototype, evaluate = DocP.evaluate;
  var XR = win.XPathResult && win.XPathResult.prototype;
  var snapLen = XR && n.getOwnPropertyDescriptor(XR, "snapshotLength").get, snapItem = XR && XR.snapshotItem;
  var AttrP = win.Attr.prototype;
  var ownerEl = n.getOwnPropertyDescriptor(AttrP, "ownerElement").get, attrName = n.getOwnPropertyDescriptor(AttrP, "name").get;
  var XS = n.XMLSerializer, serialize = XS.prototype.serializeToString;
  function compile(s) {
    if (s === "") return null;
    var m = R.apply(n.reExec, /^xpath\(([\s\S]+)\)$/, [s]);
    return m ? { x: m[1] } : { c: s };
  }
  var S = compile(sel), C = compile(chk);
  function find(doc, q) {
    var out = [], i;
    try {
      if (q.c !== undefined) {
        var l = R.apply(n.querySelectorAll, doc, [q.c]);
        for (i = 0; i < l.length; i++) out[i] = l[i];
      } else {
        var r = R.apply(evaluate, doc, [q.x, doc, null, 7, null]);
        var len = R.apply(snapLen, r, []);
        for (i = 0; i < len; i++) out[i] = R.apply(snapItem, r, [i]);
      }
    } catch (e) { return []; }
    return out;
  }
  function pruneDoc(doc) {
    if (C && !find(doc, C).length) return false;
    var t = find(doc, S), ch = false;
    for (var i = 0; i < t.length; i++) {
      try {
        if (R.nodeType(t[i]) === 2) {
          var el = R.apply(ownerEl, t[i], []);
          if (el) { R.apply(n.removeAttribute, el, [R.apply(attrName, t[i], [])]); ch = true; }
        } else { R.apply(n.remove, t[i], []); ch = true; }
      } catch (e) { /* ignore */ }
    }
    return ch;
  }
  N.editResponse({
    kind: "xml",
    test: function (req) { return UP.test(req.url); },
    run: function (text) {
      if (!R.apply(n.reTest, /^[\s﻿]*</, [text])) return null;
      var doc = N.xmlDoc(text);
      if (!doc || !pruneDoc(doc)) return null;
      var decl = R.apply(n.reExec, /^[\s﻿]*(<\?xml[^>]*\?>)/, [text]);
      var out = R.apply(serialize, new XS(), [doc]);
      if (decl && !R.startsWith(out, "<?xml")) out = decl[1] + "\n" + out;
      return out;
    },
    doc: pruneDoc
  }, "both");
}
