// @world: main
// trusted-prevent-dom-bypass (trusted only): (insertionMethodPath, [targetProp]). After the wrapped insertion
// method runs, every newly reachable same-origin iframe/frame/object/embed realm gets the parent's targetProp
// (e.g. JSON.parse, fetch, XMLHttpRequest.prototype); without targetProp the element's contentWindow /
// contentDocument report the parent window / document. Spec 03a 8.5.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 1);
  var n = R.n, win = R.win, doc = R.doc;
  var path = R.trim(A.p[0]), target = R.trim(A.p[1]);
  if (path === "") return;
  var parts = R.split(path, "."), owner = win;
  for (var i = 0; i < parts.length - 1; i++) {
    if (parts[i] === "") return;
    try { owner = owner[parts[i]]; } catch (e) { return; }
    if (!R.isObj(owner)) return;
  }
  var meth = parts[parts.length - 1];
  if (meth === "") return;
  var tparts = target === "" ? null : R.split(target, ".");
  if (tparts) for (var t = 0; t < tparts.length; t++) if (tparts[t] === "") return;
  var WS = n.WeakSet, wsHas = WS.prototype.has, wsAdd = WS.prototype.add, seen = new WS();
  // native contentWindow getters, captured before the runtime's frame hooks wrap them
  var rawCW = [];
  var ctors = ["HTMLIFrameElement", "HTMLFrameElement", "HTMLObjectElement", "HTMLEmbedElement"];
  for (var c = 0; c < ctors.length; c++) {
    var C = win[ctors[c]];
    var dw = C && n.getOwnPropertyDescriptor(C.prototype, "contentWindow");
    rawCW[c] = dw && dw.get ? dw.get : null;
  }
  var SEL = "iframe,frame,object,embed";
  var NAMES = ["IFRAME", "FRAME", "OBJECT", "EMBED"];

  function setProp(cw) {
    // walk both realms; assign at the deepest level that accepts it, else one level higher
    for (var lvl = tparts.length; lvl >= 1; lvl--) {
      var po = win, co = cw, ok = true;
      for (var k = 0; k < lvl - 1; k++) {
        try { po = po[tparts[k]]; co = co[tparts[k]]; } catch (e) { ok = false; break; }
        if (!R.isObj(po) || !R.isObj(co)) { ok = false; break; }
      }
      if (!ok) continue;
      var p = tparts[lvl - 1], pv;
      try { pv = po[p]; } catch (e) { continue; }
      var d = R.findDesc(co, p);
      try {
        if (d && d.own && !d.desc.configurable) {
          if (!d.desc.writable || d.desc.get || d.desc.set) continue;
          co[p] = pv;
          if (co[p] === pv) return true;
          continue;
        }
        var nd = d ? d.desc : { writable: true, enumerable: true, configurable: true };
        if (nd.get || nd.set) {
          if (n.defineProperty(co, p, { value: pv, writable: true, enumerable: !!nd.enumerable, configurable: true })) return true;
          continue;
        }
        if (n.defineProperty(co, p, { value: pv, writable: nd.writable !== false, enumerable: !!nd.enumerable, configurable: true })) return true;
      } catch (e) { /* try one level higher */ }
    }
    return false;
  }
  function pin(el) {
    var hw = { get contentWindow() { return win; } };
    var hd = { get contentDocument() { return doc; } };
    var gw = n.getOwnPropertyDescriptor(hw, "contentWindow").get;
    var gd = n.getOwnPropertyDescriptor(hd, "contentDocument").get;
    R.fn(gw, "function get contentWindow() { [native code] }");
    R.fn(gd, "function get contentDocument() { [native code] }");
    try {
      n.defineProperty(el, "contentWindow", { get: gw, set: undefined, enumerable: true, configurable: true });
      n.defineProperty(el, "contentDocument", { get: gd, set: undefined, enumerable: true, configurable: true });
    } catch (e) { /* ignore */ }
  }
  function handle(el) {
    if (R.apply(wsHas, seen, [el])) return;
    var idx = R.apply(n.aIndexOf, NAMES, [R.nodeName(el)]);
    if (idx === -1) return;
    var cw = null;
    if (rawCW[idx]) { try { cw = R.apply(rawCW[idx], el, []); } catch (e) { cw = null; } }
    if (!cw) return;
    try { if (!cw.Function) return; } catch (e) { return; }   // cross-origin
    R.apply(wsAdd, seen, [el]);
    // run this host's scriptlets in the child realm first, so their wrappers cannot replace what we pin below
    try { R.adopt(cw); } catch (e) { /* ignore */ }
    if (tparts) setProp(cw);
    else pin(el);
  }
  function scan(nd) {
    var nt = R.nodeType(nd);
    if (nt === 1) handle(nd);
    if (nt !== 1 && nt !== 11 && nt !== 9) return;
    var l;
    try {
      l = R.apply(nt === 1 ? n.elQuerySelectorAll : nt === 11 ? n.fragQuerySelectorAll : n.querySelectorAll, nd, [SEL]);
    } catch (e) { return; }
    var arr = R.toArray(l);
    for (var j = 0; j < arr.length; j++) handle(arr[j]);
  }
  R.wrapMethod(owner, meth, function (tf, th, a) {
    var nodes = [];
    for (var j = 0; j < a.length; j++) {
      if (!R.isObj(a[j])) continue;
      var nt = R.nodeType(a[j]);
      if (nt === 11) {   // a fragment empties itself on insertion: remember its frames first
        try { var l = R.toArray(R.apply(n.fragQuerySelectorAll, a[j], [SEL])); for (var q = 0; q < l.length; q++) R.push(nodes, l[q]); }
        catch (e) { /* ignore */ }
      } else if (nt === 1) R.push(nodes, a[j]);
    }
    var res = R.apply(tf, th, a);
    for (var m = 0; m < nodes.length; m++) { try { scan(nodes[m]); } catch (e) { /* ignore */ } }
    return res;
  });
}
