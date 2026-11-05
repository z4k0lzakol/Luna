// @world: main
// spoof-css: spoof-css(selector, prop1, value1, [prop2, value2, ...]). Special props _rectx _recty _rectw _recth
// (getBoundingClientRect fields), _debug ignored. getComputedStyle() of matching elements returns a Proxy of the
// real declaration; CSSStyleDeclaration.prototype methods (getPropertyValue, item, ...) keep their identity
// and answer for our proxies. Spec 03c 8.
function (R, ...args) {
  var n = R.n, win = R.win;
  var a = [];
  for (var i = 0; i < args.length; i++) a[i] = R.str(args[i]);
  var sel = a.length ? R.trim(a[0]) : "";
  if (sel === "") return;
  try { R.apply(n.querySelectorAll, R.doc, [sel]); } catch (e) { return; }
  var spoof = n.create(null), rect = n.create(null), any = false;
  function dashed(p) { return R.lower(R.sreplace(p, /[A-Z]/g, function (c) { return "-" + c; })); }
  function camel(p) { return R.sreplace(p, /-([a-z])/g, function (m, c) { return R.apply(n.sToUpperCase, c, []); }); }
  for (var j = 1; j + 1 < a.length; j += 2) {
    var p = R.trim(a[j]), v = a[j + 1];
    if (p === "" || p === "_debug") continue;
    if (p === "_rectx" || p === "_recty" || p === "_rectw" || p === "_recth") {
      var f = n.Number(v);
      if (f === f) { rect[p] = f; any = true; }
      continue;
    }
    var d = dashed(p);
    spoof[d] = v;
    spoof[camel(d)] = v;
    any = true;
  }
  if (!any) return;
  var WM = n.WeakMap, wmGet = WM.prototype.get, wmSet = WM.prototype.set;
  var proxies = new WM();   // proxy -> real CSSStyleDeclaration
  function matches(el) {
    try { return R.nodeType(el) === 1 && R.apply(n.matches, el, [sel]); } catch (e) { return false; }
  }
  var CSD = win.CSSStyleDeclaration && win.CSSStyleDeclaration.prototype;
  if (!CSD) return;
  var gpv = CSD.getPropertyValue;
  function realOf(th) { return R.isObj(th) ? R.apply(wmGet, proxies, [th]) : undefined; }
  // prototype methods: identity kept, our proxies answered with the real declaration as receiver
  var meths = ["getPropertyValue", "getPropertyPriority", "item", "setProperty", "removeProperty"];
  for (var m = 0; m < meths.length; m++) {
    (function (name) {
      R.wrapMethod(CSD, name, function (t, th, args2) {
        var real = realOf(th);
        if (real === undefined) return R.apply(t, th, args2);
        if (name === "getPropertyValue" && args2.length) {
          var key = R.lower(R.trim(R.str(args2[0])));
          if (R.apply(n.hasOwn, spoof, [key])) return spoof[key];
        }
        return R.apply(t, real, args2);
      });
    })(meths[m]);
  }
  var handler = {
    get: function (target, prop) {
      if (typeof prop === "string" && R.apply(n.hasOwn, spoof, [prop])) return spoof[prop];
      return n.get(target, prop, target);
    },
    set: function (target, prop, val) { return n.set(target, prop, val, target); },
    getOwnPropertyDescriptor: function (target, prop) {
      var dsc = n.getOwnPropertyDescriptor(target, prop);
      if (dsc && typeof prop === "string" && "value" in dsc && R.apply(n.hasOwn, spoof, [prop])) dsc.value = spoof[prop];
      return dsc;
    }
  };
  R.wrapMethod(win, "getComputedStyle", function (t, th, args2) {
    var cs = R.apply(t, th, args2);
    if (!args2.length || !matches(args2[0]) || !R.isObj(cs)) return cs;
    var px = new n.Proxy(cs, handler);
    R.apply(wmSet, proxies, [px, cs]);
    return px;
  });
  var DR = win.DOMRect;
  var rx = n.getOwnPropertyDescriptor(win.DOMRectReadOnly.prototype, "x").get;
  var ry = n.getOwnPropertyDescriptor(win.DOMRectReadOnly.prototype, "y").get;
  var rw = n.getOwnPropertyDescriptor(win.DOMRectReadOnly.prototype, "width").get;
  var rh = n.getOwnPropertyDescriptor(win.DOMRectReadOnly.prototype, "height").get;
  function num(s) { var f = n.Number(R.sreplace(R.trim(s), /px$/, "")); return f === f ? f : NaN; }
  R.wrapMethod(win.Element.prototype, "getBoundingClientRect", function (t, th, args2) {
    var r = R.apply(t, th, args2);
    if (!matches(th)) return r;
    var x = R.apply(rx, r, []), y = R.apply(ry, r, []), w = R.apply(rw, r, []), h = R.apply(rh, r, []);
    if (rect._rectx !== undefined) x = rect._rectx;
    if (rect._recty !== undefined) y = rect._recty;
    if (rect._rectw !== undefined) w = rect._rectw;
    else if (spoof.width !== undefined && num(spoof.width) === num(spoof.width)) w = num(spoof.width);
    if (rect._recth !== undefined) h = rect._recth;
    else if (spoof.height !== undefined && num(spoof.height) === num(spoof.height)) h = num(spoof.height);
    try { return new DR(x, y, w, h); } catch (e) { return r; }
  });
}
