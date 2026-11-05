// @world: main
// freeze-element-property: (selector, property) - semantics UNVERIFIED (spec 03c 13, 0 list uses), Luna design
// following the selector-first convention of set-attr/spoof-css: on elements matching selector (empty = any
// element) writes to the DOM property are ignored (the setter of the prototype accessor, wherever it lives in the
// HTML*Element/Element/Node chain) and setAttribute/removeAttribute/toggleAttribute of the reflected attribute
// do nothing. Reads are untouched.
function (R, ...args) {
  var A = R.safeArgs(args, 2, [], 2);
  var sel = R.trim(A.p[0]), prop = R.trim(A.p[1]);
  if (prop === "") return;
  var n = R.n, win = R.win;
  if (sel !== "") {
    try { R.apply(n.querySelector, R.doc, [sel]); } catch (e) { return; }
  }
  function hit(el) {
    if (R.nodeType(el) !== 1) return false;
    if (sel === "") return true;
    try { return R.apply(n.matches, el, [sel]); } catch (e) { return false; }
  }
  var protos = [win.Node.prototype, win.Element.prototype, win.HTMLElement.prototype];
  if (win.SVGElement) protos[protos.length] = win.SVGElement.prototype;
  var names = n.ownKeys(win);
  for (var i = 0; i < names.length; i++) {
    var k = names[i];
    if (typeof k !== "string" || !R.endsWith(k, "Element") || !(R.startsWith(k, "HTML") || R.startsWith(k, "SVG"))) continue;
    var d = n.getOwnPropertyDescriptor(win, k);
    if (d && typeof d.value === "function" && d.value.prototype) protos[protos.length] = d.value.prototype;
  }
  var setH = function (t, th, a) {
    if (hit(th)) return undefined;
    return R.apply(t, th, a);
  };
  for (var j = 0; j < protos.length; j++) {
    var pd = n.getOwnPropertyDescriptor(protos[j], prop);
    if (pd && pd.set) R.wrapAccessor(protos[j], prop, { set: setH });
  }
  var attr = R.lower(prop);
  if (attr === "classname") attr = "class";
  else if (attr === "htmlfor") attr = "for";
  var attrH = function (t, th, a) {
    if (R.lower(R.str(a[0])) === attr && hit(th)) return undefined;
    return R.apply(t, th, a);
  };
  var EP = win.Element.prototype;
  R.wrapMethod(EP, "setAttribute", attrH);
  R.wrapMethod(EP, "removeAttribute", attrH);
  R.wrapMethod(EP, "toggleAttribute", function (t, th, a) {
    if (R.lower(R.str(a[0])) === attr && hit(th)) {
      try { return R.apply(n.hasAttribute, th, [a[0]]); } catch (e) { return false; }
    }
    return R.apply(t, th, a);
  });
}
