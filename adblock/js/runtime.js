// Luna scriptlet runtime (main world). One function expression: M(win, SR, SECRET, S) -> R.
// The builder (adblock/scriptlets.py) calls it once per document; R.boot() may call it again for
// same-origin child realms (about:blank iframes) with the shared state S. See RUNTIME_API.md.
// Rules: no eval/Function/string timers/script text writes, no console, no globals, no DOM markers.
function (win, SR, SECRET, S) {
  "use strict";
  var Rf = win.Reflect, Ob = win.Object, Fp = win.Function.prototype;
  var apply = Rf.apply, construct = Rf.construct, defP = Rf.defineProperty, gOPD = Rf.getOwnPropertyDescriptor;
  var getProto = Rf.getPrototypeOf, setProto = Rf.setPrototypeOf, ownKeys = Rf.ownKeys;
  var PX = win.Proxy, WM = win.WeakMap, WS = win.WeakSet;
  var wmGet = WM.prototype.get, wmSet = WM.prototype.set, wmHas = WM.prototype.has;
  var wsHas = WS.prototype.has, wsAdd = WS.prototype.add;
  var AP = win.Array.prototype, SP = win.String.prototype, RP = win.RegExp.prototype;
  var aSlice = AP.slice, aPush = AP.push, aJoin = AP.join, aIndexOf = AP.indexOf, aSplice = AP.splice;
  var sIncludes = SP.includes, sIndexOf = SP.indexOf, sSlice = SP.slice, sSplit = SP.split, sReplace = SP.replace;
  var sStarts = SP.startsWith, sEnds = SP.endsWith, sTrim = SP.trim, sLower = SP.toLowerCase, sUpper = SP.toUpperCase;
  var reTest = RP.test, reExec = RP.exec, RX = win.RegExp, STR = win.String, NUM = win.Number;
  var FTS = Fp.toString;
  var E = win.Error, capture = E.captureStackTrace;
  var qMicro = win.queueMicrotask, sTO = win.setTimeout, cTO = win.clearTimeout;
  var EvT = win.EventTarget.prototype, addEL = EvT.addEventListener, remEL = EvT.removeEventListener;
  var EvP = win.Event.prototype, prevDef = EvP.preventDefault, stopImm = EvP.stopImmediatePropagation;
  var doc = win.document, DocP = win.Document.prototype, NodeP = win.Node.prototype, ElP = win.Element.prototype;
  var MO = win.MutationObserver, moObserve = MO.prototype.observe, moDisconnect = MO.prototype.disconnect;
  var HSE = win.HTMLScriptElement;

  function G(proto, p) { var d = proto && gOPD(proto, p); return d && d.get; }
  function SETR(proto, p) { var d = proto && gOPD(proto, p); return d && d.set; }

  var n = {
    win: win, doc: doc,
    apply: apply, construct: construct, defineProperty: defP, getOwnPropertyDescriptor: gOPD,
    getPrototypeOf: getProto, setPrototypeOf: setProto, ownKeys: ownKeys, has: Rf.has, get: Rf.get, set: Rf.set,
    create: Ob.create, keys: Ob.keys, entries: Ob.entries, freeze: Ob.freeze, assign: Ob.assign,
    hasOwn: Ob.prototype.hasOwnProperty,
    JSON_parse: win.JSON.parse, JSON_stringify: win.JSON.stringify,
    isArray: win.Array.isArray, aSlice: aSlice, aPush: aPush, aJoin: aJoin, aIndexOf: aIndexOf, aSplice: aSplice,
    aConcat: AP.concat, aMap: AP.map, aFilter: AP.filter, aForEach: AP.forEach, aIncludes: AP.includes,
    sIncludes: sIncludes, sIndexOf: sIndexOf, sSlice: sSlice, sSplit: sSplit, sReplace: sReplace,
    sStartsWith: sStarts, sEndsWith: sEnds, sTrim: sTrim, sToLowerCase: sLower, sToUpperCase: sUpper,
    sCharCodeAt: SP.charCodeAt, fromCharCode: win.String.fromCharCode,
    RegExp: RX, reTest: reTest, reExec: reExec, String: STR, Number: NUM, Boolean: win.Boolean,
    Proxy: PX, WeakMap: WM, WeakSet: WS, Map: win.Map, Set: win.Set, Promise: win.Promise,
    promiseResolve: win.Promise.resolve, promiseReject: win.Promise.reject, promiseThen: win.Promise.prototype.then,
    queueMicrotask: qMicro, setTimeout: sTO, clearTimeout: cTO,
    setInterval: win.setInterval, clearInterval: win.clearInterval,
    requestAnimationFrame: win.requestAnimationFrame,
    Error: E, TypeError: win.TypeError, ReferenceError: win.ReferenceError, captureStackTrace: capture,
    Date_now: win.Date.now, Math_random: win.Math.random, Math_floor: win.Math.floor,
    Math_min: win.Math.min, Math_max: win.Math.max,
    atob: win.atob, btoa: win.btoa, encodeURIComponent: win.encodeURIComponent,
    decodeURIComponent: win.decodeURIComponent, URL: win.URL, URLSearchParams: win.URLSearchParams,
    TextEncoder: win.TextEncoder, TextDecoder: win.TextDecoder, DOMParser: win.DOMParser,
    XMLSerializer: win.XMLSerializer, Blob: win.Blob,
    fetch: win.fetch, Request: win.Request, Response: win.Response, Headers: win.Headers,
    XMLHttpRequest: win.XMLHttpRequest, FTS: FTS,
    MutationObserver: MO, moObserve: moObserve, moDisconnect: moDisconnect,
    addEventListener: addEL, removeEventListener: remEL, dispatchEvent: EvT.dispatchEvent,
    preventDefault: prevDef, stopImmediatePropagation: stopImm,
    querySelector: DocP.querySelector, querySelectorAll: DocP.querySelectorAll,
    createElement: DocP.createElement, getElementById: DocP.getElementById,
    createTreeWalker: DocP.createTreeWalker, twNext: win.TreeWalker.prototype.nextNode,
    elQuerySelector: ElP.querySelector, elQuerySelectorAll: ElP.querySelectorAll,
    fragQuerySelectorAll: win.DocumentFragment.prototype.querySelectorAll,
    matches: ElP.matches, closest: ElP.closest, getAttribute: ElP.getAttribute, setAttribute: ElP.setAttribute,
    removeAttribute: ElP.removeAttribute, hasAttribute: ElP.hasAttribute, remove: ElP.remove,
    replaceWith: ElP.replaceWith, cloneNode: NodeP.cloneNode, appendChild: NodeP.appendChild,
    contains: NodeP.contains, getComputedStyle: win.getComputedStyle,
    getBoundingClientRect: ElP.getBoundingClientRect,
    nodeTypeGet: G(NodeP, "nodeType"), nodeNameGet: G(NodeP, "nodeName"), parentNodeGet: G(NodeP, "parentNode"),
    textContentGet: G(NodeP, "textContent"), textContentSet: SETR(NodeP, "textContent"),
    nodeValueGet: G(NodeP, "nodeValue"), nodeValueSet: SETR(NodeP, "nodeValue"),
    isConnectedGet: G(NodeP, "isConnected"), defaultViewGet: G(DocP, "defaultView"),
    currentScriptGet: G(DocP, "currentScript"), readyStateGet: G(DocP, "readyState"),
    documentElementGet: G(DocP, "documentElement"), headGet: G(DocP, "head"), bodyGet: G(DocP, "body"),
    cookieGet: G(DocP, "cookie"), cookieSet: SETR(DocP, "cookie"),
    scriptSrcGet: G(HSE.prototype, "src"), scriptTypeGet: G(HSE.prototype, "type"),
    iframeContentWindowGet: G(win.HTMLIFrameElement.prototype, "contentWindow"),
    objectContentWindowGet: G(win.HTMLObjectElement.prototype, "contentWindow"),
    HTMLScriptElement: HSE, HTMLElement: win.HTMLElement, Element: win.Element, Node: win.Node,
    Document: win.Document, Window: win.Window, location: win.location
  };

  // ------------------------------------------------------------ shared state (one per same-origin realm tree)
  function sameOriginAncestors() {
    var out = [], p = win;
    try {
      while (p.parent && p.parent !== p) {
        p = p.parent;
        var k = p.Function.prototype;   // throws for cross-origin
        if (!k) break;
        out[out.length] = p;
      }
    } catch (e) { /* stop at the first cross-origin ancestor */ }
    return out;
  }
  var ANC = sameOriginAncestors();
  if (!S) {
    for (var ai = 0; ai < ANC.length && !S; ai++) {
      try {
        var fts = ANC[ai].Function.prototype.toString;
        // only our masking proxy prints like this (an unmasked Proxy of a native function)
        if (apply(FTS, fts, []) === "function () { [native code] }") {
          var got = apply(fts, SECRET, []);
          if (got && typeof got === "object" && got.reg) S = got;
        }
      } catch (e) { /* not ours */ }
    }
  }
  if (!S) {
    S = { reg: new WM(), masked: new WS(), realms: new WS(), errl: new WS(), errs: new WS(), hooked: new WS(),
          defs: new WM(), ins: new WM(), pending: 0, on: false };
  }

  var R = { n: n, win: win, doc: doc, SR: typeof SR === "string" ? SR : "", S: S, apply: apply };

  // ------------------------------------------------------------ toString masking
  var RE_TRAP_FRAME = /^\s*at Object\.apply \([^()]*\)$/;
  function scrubTrapFrame(e) {
    try {
      // V8 (Chromium 140): "stack" is an own accessor pair; older builds: an own data property
      var d = gOPD(e, "stack");
      if (!d) return;
      var s = d.get ? apply(d.get, e, []) : d.value;
      if (typeof s !== "string") return;
      var lines = apply(sSplit, s, ["\n"]), out = [], done = false;
      for (var i = 0; i < lines.length; i++) {
        if (!done && i > 0 && apply(reTest, RE_TRAP_FRAME, [lines[i]])) { done = true; continue; }
        out[out.length] = lines[i];
      }
      if (!done) return;
      s = apply(aJoin, out, ["\n"]);
      if (d.set) apply(d.set, e, [s]);
      else if ("value" in d) defP(e, "stack", { value: s, writable: d.writable, enumerable: d.enumerable, configurable: d.configurable });
    } catch (x) { /* ignore */ }
  }
  function installMask(w) {
    var fp;
    try { fp = w.Function.prototype; } catch (e) { return; }
    if (!fp || apply(wsHas, S.masked, [fp])) return;
    apply(wsAdd, S.masked, [fp]);
    var d = gOPD(fp, "toString");
    if (!d || typeof d.value !== "function") return;
    var nts = d.value;
    var p = new w.Proxy(nts, {
      apply: function (t, th, a) {
        if (th === SECRET) return S;
        var m = apply(wmGet, S.reg, [th]);
        if (m !== undefined) {
          if (typeof m === "string") return m;
          th = m;
        }
        if (typeof th !== "function") {   // native throws: hide this trap's frame from the error's stack
          try { return apply(t, th, a); } catch (e) { scrubTrapFrame(e); throw e; }
        }
        return apply(t, th, a);
      }
    });
    apply(wmSet, S.reg, [p, nts]);
    defP(fp, "toString", { value: p, writable: d.writable, enumerable: d.enumerable, configurable: d.configurable });
  }
  function ensureMask() {
    if (R.masked) return;
    R.masked = true;
    S.on = true;
    installMask(win);
    for (var i = 0; i < ANC.length; i++) installMask(ANC[i]);
  }
  // fake: function/proxy to disguise; nat: the native function it should print as, or the exact text
  function mask(fake, nat) {
    if ((typeof fake !== "function") || (typeof nat !== "function" && typeof nat !== "string")) return fake;
    ensureMask();
    if (typeof nat === "function") {   // wrapping a wrapper: point straight at the innermost native
      var inner = apply(wmGet, S.reg, [nat]);
      if (inner !== undefined) nat = inner;
    }
    apply(wmSet, S.reg, [fake, nat]);
    return fake;
  }
  // for functions WE create (not proxies): give them this realm's Function.prototype, then mask with text
  function ownFn(f, text) {
    try { if (getProto(f) !== Fp) setProto(f, Fp); } catch (e) { /* ignore */ }
    return mask(f, typeof text === "string" ? text : "function () {}");
  }
  function anon(f) { return f; }   // passing a function expression through a call keeps its name ""
  R.mask = mask;
  R.fn = ownFn;
  R.anon = anon;

  // ------------------------------------------------------------ silent aborts
  function onErr(ev) {
    if (S.pending > 0) {
      S.pending = 0;
      apply(prevDef, ev, []);
      apply(stopImm, ev, []);
    }
  }
  function onRej(ev) {
    var r;
    try { r = ev.reason; } catch (e) { return; }
    if (r !== null && typeof r === "object" && apply(wsHas, S.errs, [r])) {
      apply(prevDef, ev, []);
      apply(stopImm, ev, []);
    }
  }
  if (!apply(wsHas, S.errl, [Fp])) {
    apply(wsAdd, S.errl, [Fp]);
    try {
      apply(addEL, win, ["error", onErr, true]);
      apply(addEL, win, ["unhandledrejection", onRej, true]);
    } catch (e) { /* ignore */ }
  }
  function clearPending() { S.pending = 0; }
  // throws a page-realm ReferenceError "<msg>"; the uncaught error event is swallowed silently
  // above: the outermost of our functions the page called (accessor / trap); its frames are cut from e.stack
  R.abort = function (msg, above) {
    var e = new win.ReferenceError(typeof msg === "string" ? msg : "");
    try { apply(capture, E, [e, typeof above === "function" ? above : R.abort]); } catch (x) { /* ignore */ }
    try { apply(wsAdd, S.errs, [e]); } catch (x) { /* ignore */ }
    S.pending++;
    try { apply(qMicro, win, [clearPending]); } catch (x) { S.pending = 0; }
    throw e;
  };
  R.abortMsg = function (chain) {
    var parts = apply(sSplit, STR(chain || ""), ["."]);
    var last = parts[parts.length - 1] || "x";
    return last + " is not defined";
  };

  // ------------------------------------------------------------ small safe helpers
  R.log = function () {};
  R.isObj = function (v) { return v !== null && (typeof v === "object" || typeof v === "function"); };
  R.str = function (v) {   // primitive -> String(v); anything else -> "" (never runs page code)
    var t = typeof v;
    if (t === "string") return v;
    if (t === "number" || t === "boolean" || t === "bigint" || t === "undefined") return STR(v);
    if (v === null) return "null";
    return "";
  };
  R.fnText = function (x) {   // stringifyCallback: function source / primitive / ""
    if (typeof x === "function") { try { return apply(FTS, x, []); } catch (e) { return ""; } }
    var t = typeof x;
    if (t === "string" || t === "number" || t === "boolean" || t === "bigint") return STR(x);
    return "";
  };
  R.includes = function (s, sub) { return apply(sIncludes, s, [sub]); };
  R.indexOf = function (s, sub) { return apply(sIndexOf, s, [sub]); };
  R.split = function (s, sep) { return apply(sSplit, s, [sep]); };
  R.slice = function (x, a, b) { return apply(typeof x === "string" ? sSlice : aSlice, x, b === undefined ? [a] : [a, b]); };
  R.trim = function (s) { return apply(sTrim, s, []); };
  R.lower = function (s) { return apply(sLower, s, []); };
  R.startsWith = function (s, p) { return apply(sStarts, s, [p]); };
  R.endsWith = function (s, p) { return apply(sEnds, s, [p]); };
  R.sreplace = function (s, a, b) { return apply(sReplace, s, [a, b]); };
  R.push = function (arr, v) { arr[arr.length] = v; return arr; };
  R.join = function (arr, sep) { return apply(aJoin, arr, [sep]); };
  R.toArray = function (x) { return apply(aSlice, x, [0]); };
  R.now = function () { return apply(n.Date_now, win.Date, []); };
  R.later = function (fn, ms) {   // pristine setTimeout with a function callback (never a string)
    return apply(sTO, win, [function () { try { fn(); } catch (e) { /* ignore */ } }, ms || 0]);
  };

  // ------------------------------------------------------------ patterns
  var RE_LIT = /^\/(.+)\/([gimsu]*)$/s;
  function stripGY(f) { return apply(sReplace, f, [/[gy]/g, ""]); }
  // raw: filter argument; negatable: honour a leading "!"
  R.pattern = function (raw, negatable) {
    var s = R.str(raw), neg = false;
    if (negatable && s.charAt(0) === "!") { neg = true; s = apply(sSlice, s, [1]); }
    var P = { kind: "all", neg: neg, text: s, re: null, src: s };
    if (s !== "") {
      var m = apply(reExec, RE_LIT, [s]);
      var re = null;
      if (m) {
        try { re = new RX(m[1], m[2]); } catch (e) { re = null; }
      }
      if (re) { P.kind = "regex"; P.re = re; P.tre = (m[2] === stripGY(m[2])) ? re : new RX(m[1], stripGY(m[2])); }
      else P.kind = "literal";
    }
    P.test = function (text) {
      var t = typeof text === "string" ? text : R.str(text), r;
      if (P.kind === "all") r = true;
      else if (P.kind === "literal") r = apply(sIncludes, t, [P.text]);
      else { P.tre.lastIndex = 0; r = apply(reTest, P.tre, [t]); }
      return P.neg ? !r : r;
    };
    return P;
  };
  // exact-or-regex matcher (aeld event types): plain string = whole-string equality
  R.exactPattern = function (raw) {
    var P = R.pattern(raw, false);
    if (P.kind === "literal") P.test = function (t) { return t === P.text; };
    return P;
  };
  // delay matcher for timers: "N", "A-B", "A-", "-B", optional "!" -> fn(d)->bool, or null if unparseable
  R.delayMatcher = function (raw) {
    var s = R.trim(R.str(raw)), neg = false;
    if (s === "") return function () { return true; };
    if (s.charAt(0) === "!") { neg = true; s = apply(sSlice, s, [1]); }
    var m = apply(reExec, /^(\d+)?(-)?(\d+)?$/, [s]);
    if (!m || (m[1] === undefined && m[3] === undefined)) return null;
    var lo = m[1] !== undefined ? NUM(m[1]) : -Infinity, hi = m[3] !== undefined ? NUM(m[3]) : Infinity;
    if (!m[2]) { if (m[3] !== undefined) return null; hi = lo; }
    return function (d) { var r = d >= lo && d <= hi; return neg ? !r : r; };
  };
  R.delayOf = function (v) {   // timer delay as the browser would see it, without running page code
    var t = typeof v, d = 0;
    if (t === "number") d = v;
    else if (t === "string" || t === "boolean") d = NUM(v);
    d = apply(n.Math_floor, win.Math, [d]);
    return (d !== d || d < 0) ? 0 : d;
  };

  // ------------------------------------------------------------ args / varargs
  // args: array of strings; npos: number of positional slots; names: known vararg names; req: required slots
  R.safeArgs = function (args, npos, names, req) {
    var a = [], i, out = { p: [], x: Ob.create(null) };
    for (i = 0; i < (args ? args.length : 0); i++) a[i] = R.str(args[i]);
    names = names || [];
    req = req === undefined ? 1 : req;
    var start = npos;
    for (i = req; i < npos && i < a.length; i++) {
      if (apply(aIndexOf, names, [a[i]]) !== -1) { start = i; break; }
    }
    for (i = 0; i < npos; i++) out.p[i] = i < start && i < a.length ? a[i] : "";
    for (i = start; i < a.length; i += 2) out.x[a[i]] = i + 1 < a.length ? a[i + 1] : "";
    return out;
  };

  // ------------------------------------------------------------ constants (validateConstant)
  function constFn(kind, extra) {
    if (kind === "noopFunc") return ownFn(anon(function () {}), "function () {}");
    if (kind === "trueFunc") return ownFn(anon(function () { return true; }), "function () { return true; }");
    if (kind === "falseFunc") return ownFn(anon(function () { return false; }), "function () { return false; }");
    if (kind === "throwFunc") {
      var tf = anon(function () { R.abort(extra, tf); });
      return ownFn(tf, "function () { throw new Error(); }");
    }
    if (kind === "noopCallbackFunc") {
      return ownFn(anon(function () { return ownFn(anon(function () {}), "function () {}"); }),
        "function () { return function () {}; }");
    }
    if (kind === "noopPromiseResolve") {
      return ownFn(anon(function () { return apply(n.promiseResolve, n.Promise, [new n.Response()]); }),
        "function () { return Promise.resolve(new Response()); }");
    }
    if (kind === "noopPromiseReject") {
      return ownFn(anon(function () { return apply(n.promiseReject, n.Promise, []); }),
        "function () { return Promise.reject(); }");
    }
    return undefined;
  }
  // raw token -> {v: value} or null (invalid -> scriptlet must stay inert). name: chain (for throwFunc msg)
  R.constant = function (raw, trusted, name) {
    var t = R.str(raw), u = t;
    if ((t.length >= 2) && ((t.charAt(0) === "'" && t.charAt(t.length - 1) === "'") ||
        (t.charAt(0) === '"' && t.charAt(t.length - 1) === '"'))) {
      if (t.length === 2) return { v: "" };
    }
    switch (u) {
      case "undefined": return { v: undefined };
      case "false": return { v: false };
      case "true": return { v: true };
      case "null": return { v: null };
      case "": return { v: "" };
      case "yes": return { v: "yes" };
      case "no": return { v: "no" };
      case "[]": case "emptyArr": return { v: [] };
      case "{}": case "emptyObj": return { v: {} };
      case "noopFunc": case "trueFunc": case "falseFunc": case "throwFunc": case "noopCallbackFunc":
      case "noopPromiseResolve": case "noopPromiseReject":
        return { v: constFn(u, R.abortMsg(name)) };
    }
    if (apply(reTest, /^-?\d+$/, [u])) {
      var num = NUM(u);
      if (num >= -32767 && num <= 32767) return { v: num };
      if (!trusted) return null;
    }
    if (!trusted) return null;
    try {
      if (apply(sStarts, u, ["json:"])) return { v: apply(n.JSON_parse, win.JSON, [apply(sSlice, u, [5])]) };
      if (u.charAt(0) === "{" && u.charAt(u.length - 1) === "}") {
        var o = apply(n.JSON_parse, win.JSON, [u]);
        return { v: o && typeof o === "object" ? o.value : undefined };
      }
    } catch (e) { return null; }
    return { v: u };
  };

  // ------------------------------------------------------------ descriptors / defining
  R.findDesc = function (o, p) {   // {desc, holder, own} along the prototype chain, or null
    var h = o, first = true;
    while (h !== null && h !== undefined) {
      var d;
      try { d = gOPD(h, p); } catch (e) { return null; }
      if (d) return { desc: d, holder: h, own: first };
      first = false;
      try { h = getProto(h); } catch (e) { return null; }
    }
    return null;
  };
  // replace a property's value keeping its attributes (inherited -> own with the same attributes)
  R.redefine = function (o, p, v) {
    var f = R.findDesc(o, p);
    var d = f ? f.desc : { writable: true, enumerable: true, configurable: true };
    if (f && f.own && !d.configurable) {
      if (d.writable) { try { o[p] = v; return true; } catch (e) { return false; } }
      return false;
    }
    return defP(o, p, { value: v, writable: d.writable !== false, enumerable: !!d.enumerable,
                        configurable: d.configurable !== false });
  };
  // masked Proxy around target. h = Proxy handler object
  R.proxy = function (target, h) {
    var p = new PX(target, h);
    mask(p, target);
    return p;
  };
  // wrap obj[prop] (a function) with an apply trap h(target, thisArg, argsArray). Returns the proxy or null
  R.wrapMethod = function (o, p, h) {
    var f = R.findDesc(o, p);
    if (!f || typeof f.desc.value !== "function") return null;
    var px = R.proxy(f.desc.value, { apply: h });
    return R.redefine(o, p, px) ? px : null;
  };
  // wrap a constructor/function with construct (and optional apply) traps
  R.wrapCtor = function (o, p, hc, ha) {
    var f = R.findDesc(o, p);
    if (!f || typeof f.desc.value !== "function") return null;
    var h = { construct: hc };
    if (ha) h.apply = ha;
    var px = R.proxy(f.desc.value, h);
    return R.redefine(o, p, px) ? px : null;
  };
  // wrap an accessor's getter/setter with apply traps: hs = {get: h(t, this, args), set: h(t, this, [v])}
  R.wrapAccessor = function (o, p, hs) {
    var f = R.findDesc(o, p);
    if (!f || !(f.desc.get || f.desc.set)) return false;
    var d = f.desc, nd = { configurable: d.configurable, enumerable: d.enumerable, get: d.get, set: d.set };
    if (hs.get && d.get) nd.get = R.proxy(d.get, { apply: hs.get });
    if (hs.set && d.set) nd.set = R.proxy(d.set, { apply: hs.set });
    if (f.own && !d.configurable) return false;
    return defP(f.own ? o : f.holder, p, nd);
  };
  // define a masked accessor whose functions are named "get p"/"set p" like natives
  R.defineAccessor = function (o, p, getf, setf, enumerable) {
    var holder = {
      get [p]() { return getf(this); },
      set [p](v) { setf(this, v); }
    };
    var d = gOPD(holder, p);
    ownFn(d.get, "function get " + p + "() { [native code] }");
    ownFn(d.set, "function set " + p + "() { [native code] }");
    var ok = defP(o, p, { configurable: true, enumerable: enumerable !== false, get: d.get, set: d.set });
    return ok ? d : null;
  };

  // ------------------------------------------------------------ property-chain traps
  // spec: {init(st)->false to give up, get(st, receiver), set(st, v, receiver),
  //        defer: "any" (default) | "strict" (set-constant rules) | "none" (trap first missing segment),
  //        fixed(o, p, desc) for non-configurable own leaves}
  // st: {owner, prop, desc (found along proto chain or undefined), own, value, fnGet, fnSet}
  function isObjLike(v) { return v !== null && (typeof v === "object" || typeof v === "function"); }
  function deferRec(o, p) {
    var m = apply(wmGet, S.defs, [o]);
    return m ? m[p] : undefined;
  }
  R.passGet = function (st, rcv) {
    if (st.desc && st.desc.get) return apply(st.desc.get, rcv, []);
    return st.value;
  };
  R.passSet = function (st, v, rcv) {
    if (st.desc && st.desc.set) { apply(st.desc.set, rcv, [v]); return; }
    if (st.desc && st.desc.get) return;
    if (rcv !== st.owner && isObjLike(rcv)) {   // write through an inheriting object: create own data prop
      defP(rcv, st.prop, { value: v, writable: true, enumerable: true, configurable: true });
      return;
    }
    st.value = v;
  };
  R.trap = function (owner, chain, spec) {
    if (!isObjLike(owner) || typeof chain !== "string" || chain === "") return false;
    var parts = apply(sSplit, chain, ["."]);
    for (var i = 0; i < parts.length; i++) if (parts[i] === "") return false;
    var mode = spec.defer || "any";
    function leaf(o, p) {
      var f = R.findDesc(o, p);
      var own = !!(f && f.own), d = f ? f.desc : undefined;
      if (own && !d.configurable) return spec.fixed ? !!spec.fixed(o, p, d) : false;
      var st = { owner: o, prop: p, desc: d, own: own, value: undefined, fnGet: null, fnSet: null };
      if (d && !d.get && !d.set) st.value = d.value;
      if (spec.init && spec.init(st) === false) return false;
      var acc = R.defineAccessor(o, p,
        function (rcv) { return spec.get ? spec.get(st, rcv) : R.passGet(st, rcv); },
        function (rcv, v) { if (spec.set) spec.set(st, v, rcv); else R.passSet(st, v, rcv); },
        d ? d.enumerable : true);
      if (!acc) return false;
      st.fnGet = acc.get; st.fnSet = acc.set;
      return true;
    }
    function step(o, i) {
      var p = parts[i];
      if (i === parts.length - 1) return leaf(o, p);
      var rec = deferRec(o, p);
      if (rec) {
        var cd = gOPD(o, p);
        if (cd && cd.get === rec.get) {   // our own deferral accessor: chain onto it
          rec.subs[rec.subs.length] = function (nv) { step(nv, i + 1); };
          if (isObjLike(rec.cur)) return step(rec.cur, i + 1);
          return true;
        }
      }
      var v;
      try { v = o[p]; } catch (e) { return false; }
      if (isObjLike(v)) return step(v, i + 1);
      if (mode === "none") return leaf(o, p);
      var d = gOPD(o, p);
      if (d && !d.configurable) return false;
      if (mode === "strict") {
        if (d ? (d.get || d.set) : (p in o)) return false;
      }
      rec = { cur: v, subs: [], get: null };
      rec.subs[0] = function (nv) { step(nv, i + 1); };
      var acc = R.defineAccessor(o, p,
        function () { return rec.cur; },
        function (rcv, nv) {
          rec.cur = nv;
          if (isObjLike(nv)) {
            for (var k = 0; k < rec.subs.length; k++) { try { rec.subs[k](nv); } catch (e) { /* ignore */ } }
          }
        },
        d ? d.enumerable : true);
      if (!acc) return false;
      rec.get = acc.get;
      var m = apply(wmGet, S.defs, [o]);
      if (!m) { m = Ob.create(null); apply(wmSet, S.defs, [o, m]); }
      m[p] = rec;
      return true;
    }
    try { return step(owner, 0); } catch (e) { return false; }
  };

  // ------------------------------------------------------------ stacks
  var docURL = "";
  try { docURL = apply(sSplit, STR(win.location.href), ["#"])[0]; } catch (e) { docURL = ""; }
  var RE_FRAME = /^\s*at\s+(?:(.*?)\s+\((.*)\)|(.*))$/;
  var RE_LOC = /^(.*):(\d+):(\d+)$/;
  function normFrame(line) {
    var m = apply(reExec, RE_FRAME, [line]);
    if (!m) return null;
    var fn = m[1] !== undefined ? m[1] : "", loc = m[1] !== undefined ? m[2] : m[3];
    if (apply(sStarts, fn, ["async "])) fn = apply(sSlice, fn, [6]);
    if (apply(sStarts, fn, ["new "])) fn = apply(sSlice, fn, [4]);
    fn = apply(sReplace, fn, [/ \[as [^\]]*\]$/, ""]);
    var url, ln;
    if (apply(sStarts, loc, ["eval at "]) || apply(sIncludes, loc, ["(eval at "])) {
      var lm = apply(reExec, RE_LOC, [loc]);
      url = "injectedScript"; ln = lm ? lm[2] : "1";
    } else {
      var lm2 = apply(reExec, RE_LOC, [loc]);
      if (!lm2) return null;            // native/builtin frame without a position
      url = lm2[1]; ln = lm2[2];
      if (url === "<anonymous>" || url === "") url = "injectedScript";
      else if (url === docURL) url = "inlineScript";
    }
    return fn + "@" + url + ":" + ln + ":1";
  }
  // normalised stack "stackDepth:N\tfn@url:L:1\t..." of the page code that called `above`
  // (above = the accessor/trap function the page invoked; it and our frames inside it are omitted)
  R.stack = function (above) {
    var dP = gOPD(E, "prepareStackTrace"), dL = gOPD(E, "stackTraceLimit");
    var okP = !dP || ("value" in dP && dP.configurable), okL = !dL || ("value" in dL && dL.configurable);
    var o = {}, s = "";
    try {
      if (okP && dP) defP(E, "prepareStackTrace", { value: undefined, writable: true, enumerable: dP.enumerable, configurable: true });
      if (okL) defP(E, "stackTraceLimit", { value: 50, writable: true, enumerable: dL ? dL.enumerable : true, configurable: true });
      apply(capture, E, [o, typeof above === "function" ? above : R.stack]);
      s = o.stack;
    } catch (e) { s = ""; }
    finally {
      if (okP) { if (dP) defP(E, "prepareStackTrace", dP); }
      if (okL) { if (dL) defP(E, "stackTraceLimit", dL); else delete E.stackTraceLimit; }
    }
    if (typeof s !== "string") s = "";
    var lines = apply(sSplit, s, ["\n"]), out = [];
    for (var i = 1; i < lines.length; i++) {
      var f = normFrame(lines[i]);
      if (f !== null) out[out.length] = f;
    }
    return "stackDepth:" + out.length + "\t" + apply(aJoin, out, ["\t"]);
  };

  // ------------------------------------------------------------ timing / DOM helpers
  R.readyState = function () { try { return apply(n.readyStateGet, doc, []); } catch (e) { return "loading"; } };
  // when: ""|"loading"|"1" now; "interactive"|"end"|"2" DOMContentLoaded; "complete"|"idle"|"3" load
  R.onReady = function (fn, when) {
    var w = R.str(when), lvl = 1;
    if (w === "interactive" || w === "end" || w === "2") lvl = 2;
    else if (w === "complete" || w === "idle" || w === "3") lvl = 3;
    var rs = R.readyState();
    if (lvl === 1 || (lvl === 2 && rs !== "loading") || (lvl === 3 && rs === "complete")) {
      try { fn(); } catch (e) { /* ignore */ }
      return;
    }
    var cb = function () { try { fn(); } catch (e) { /* ignore */ } };
    apply(addEL, lvl === 2 ? doc : win, [lvl === 2 ? "DOMContentLoaded" : "load", cb, { once: true, capture: true }]);
  };
  R.nodeName = function (nd) { try { return apply(n.nodeNameGet, nd, []); } catch (e) { return ""; } };
  R.nodeType = function (nd) { try { return apply(n.nodeTypeGet, nd, []); } catch (e) { return 0; } };
  R.parent = function (nd) { try { return apply(n.parentNodeGet, nd, []); } catch (e) { return null; } };
  R.isScript = function (nd) { return R.nodeName(nd) === "SCRIPT"; };
  R.text = function (nd) {
    try { return R.nodeType(nd) === 1 ? apply(n.textContentGet, nd, []) || "" : apply(n.nodeValueGet, nd, []) || ""; }
    catch (e) { return ""; }
  };
  // write text of a non-script node. Script text is never written (Trusted Types sink): returns false
  R.setText = function (nd, t) {
    var nt = R.nodeType(nd);
    if (nt === 1) {
      if (R.isScript(nd)) return false;
      try { apply(n.textContentSet, nd, [t]); return true; } catch (e) { return false; }
    }
    if (R.isScript(R.parent(nd))) return false;
    try { apply(n.nodeValueSet, nd, [t]); return true; } catch (e) { return false; }
  };
  // replace a not-yet-executed script element with an empty shallow clone (same attributes, no text)
  R.emptyScript = function (el) {
    try {
      var c = apply(n.cloneNode, el, [false]);
      apply(n.replaceWith, el, [c]);
      return c;
    } catch (e) { return null; }
  };
  R.observe = function (target, opts, cb) {   // pristine MutationObserver; returns stop()
    var mo = new MO(function (recs) { try { cb(recs); } catch (e) { /* ignore */ } });
    try { apply(moObserve, mo, [target, opts]); } catch (e) { return function () {}; }
    return function () { try { apply(moDisconnect, mo, []); } catch (e) { /* ignore */ } };
  };

  // ------------------------------------------------------------ dynamic <script> insertion / document.write
  var JS_TYPES = ["", "module", "text/javascript", "application/javascript", "application/ecmascript",
    "application/x-ecmascript", "application/x-javascript", "text/ecmascript", "text/javascript1.0",
    "text/javascript1.1", "text/javascript1.2", "text/javascript1.3", "text/javascript1.4", "text/javascript1.5",
    "text/jscript", "text/livescript", "text/x-ecmascript", "text/x-javascript"];
  R.isExecutableScript = function (el) {
    var t;
    try { t = apply(n.getAttribute, el, ["type"]); } catch (e) { return false; }
    if (t === null) return true;
    return apply(aIndexOf, JS_TYPES, [apply(sLower, apply(sTrim, t, []), [])]) !== -1;
  };
  function insState() {
    var st = apply(wmGet, S.ins, [Fp]);
    if (!st) { st = { fns: [], wfns: [], hooked: false, whooked: false }; apply(wmSet, S.ins, [Fp, st]); }
    return st;
  }
  function scriptsIn(nd, out) {
    var t = R.nodeType(nd);
    if (t === 1) {
      if (R.isScript(nd)) { out[out.length] = nd; return; }
      try { var l = apply(n.elQuerySelectorAll, nd, ["script"]); for (var i = 0; i < l.length; i++) out[out.length] = l[i]; }
      catch (e) { /* ignore */ }
    } else if (t === 11) {
      try { var l2 = apply(n.fragQuerySelectorAll, nd, ["script"]); for (var j = 0; j < l2.length; j++) out[out.length] = l2[j]; }
      catch (e) { /* ignore */ }
    }
  }
  function insHook(t, th, a) {
    var st = insState(), changed = null;
    if (st.fns.length) {
      var found = [];
      for (var i = 0; i < a.length; i++) if (R.isObj(a[i])) scriptsIn(a[i], found);
      for (var k = 0; k < found.length; k++) {
        var el = found[k], hit = false;
        for (var f = 0; f < st.fns.length && !hit; f++) { try { hit = st.fns[f](el) === true; } catch (e) { /* ignore */ } }
        if (hit) {
          var old = null;
          try { old = apply(n.getAttribute, el, ["type"]); apply(n.setAttribute, el, ["type", "text/plain"]); }
          catch (e) { continue; }
          if (!changed) changed = [];
          changed[changed.length] = [el, old];
        }
      }
    }
    try { return apply(t, th, a); }
    finally {
      if (changed) {
        for (var c = 0; c < changed.length; c++) {
          try {
            if (changed[c][1] === null) apply(n.removeAttribute, changed[c][0], ["type"]);
            else apply(n.setAttribute, changed[c][0], ["type", changed[c][1]]);
          } catch (e) { /* ignore */ }
        }
      }
    }
  }
  // fn(scriptEl) -> true to prevent execution of a dynamically inserted <script> (type is switched around
  // the native insertion and restored afterwards). Returns a remover.
  R.onScriptInsert = function (fn) {
    var st = insState();
    st.fns[st.fns.length] = fn;
    if (!st.hooked) {
      st.hooked = true;
      var targets = [[NodeP, ["appendChild", "insertBefore", "replaceChild"]],
        [ElP, ["append", "prepend", "before", "after", "replaceWith", "insertAdjacentElement", "replaceChildren"]],
        [DocP, ["append", "prepend", "replaceChildren"]],
        [win.DocumentFragment.prototype, ["append", "prepend", "replaceChildren"]],
        [win.CharacterData.prototype, ["before", "after", "replaceWith"]]];
      for (var i = 0; i < targets.length; i++) {
        for (var j = 0; j < targets[i][1].length; j++) {
          try { R.wrapMethod(targets[i][0], targets[i][1][j], insHook); } catch (e) { /* ignore */ }
        }
      }
    }
    return function () { var k = apply(aIndexOf, st.fns, [fn]); if (k !== -1) apply(aSplice, st.fns, [k, 1]); };
  };
  // fn(html) -> new html for document.write/writeln (only plain-string calls are edited)
  R.onWrite = function (fn) {
    var st = insState();
    st.wfns[st.wfns.length] = fn;
    if (!st.whooked) {
      st.whooked = true;
      var h = function (t, th, a) {
        var all = true, i;
        for (i = 0; i < a.length; i++) if (typeof a[i] !== "string") { all = false; break; }
        if (all && a.length && st.wfns.length) {
          var html = apply(aJoin, a, [""]), orig = html;
          for (i = 0; i < st.wfns.length; i++) { try { var r = st.wfns[i](html); if (typeof r === "string") html = r; } catch (e) { /* ignore */ } }
          if (html !== orig) return apply(t, th, [html]);
        }
        return apply(t, th, a);
      };
      R.wrapMethod(DocP, "write", h);
      R.wrapMethod(DocP, "writeln", h);
    }
    return function () { var k = apply(aIndexOf, st.wfns, [fn]); if (k !== -1) apply(aSplice, st.wfns, [k, 1]); };
  };

  // ------------------------------------------------------------ Trusted Types (lazy, one policy per realm)
  // R.trusted("script"|"html", text) -> value accepted by the matching sink: TrustedScript/TrustedHTML from a
  // policy created on first use (random name), the plain string when the realm has no Trusted Types, or null
  // when the policy cannot be created (CSP name allowlist) -> the caller must not write.
  var TTF = null, ttCreate = null, ttScript = null, ttHTML = null, ttPol;
  try {
    TTF = win.trustedTypes || null;
    if (TTF) {
      ttCreate = win.TrustedTypePolicyFactory.prototype.createPolicy;
      ttScript = win.TrustedTypePolicy.prototype.createScript;
      ttHTML = win.TrustedTypePolicy.prototype.createHTML;
    }
  } catch (e) { TTF = null; }
  R.trusted = function (kind, s) {
    s = R.str(s);
    if (!TTF || !ttCreate) return s;
    if (ttPol === undefined) {
      ttPol = null;
      var nm = "", AZ = "abcdefghijklmnopqrstuvwxyz";
      for (var k = 0; k < 10; k++) {
        var ci = apply(n.Math_floor, win.Math, [apply(n.Math_random, win.Math, []) * 26]);
        nm += apply(sSlice, AZ, [ci, ci + 1]);
      }
      var id = function (x) { return x; };
      try { ttPol = apply(ttCreate, TTF, [nm, { createScript: id, createHTML: id }]); } catch (e) { ttPol = null; }
    }
    if (!ttPol) return null;
    try { return apply(kind === "html" ? ttHTML : ttScript, ttPol, [s]); } catch (e) { return null; }
  };

  // ------------------------------------------------------------ frames
  R.ancestorHosts = function () {
    var out = [];
    try {
      var ao = win.location.ancestorOrigins;
      for (var i = 0; ao && i < ao.length; i++) {
        var h = "";
        try { h = new n.URL(ao[i]).hostname; } catch (e) { h = ""; }
        out[out.length] = h;
      }
    } catch (e) { /* ignore */ }
    return out;
  };
  R.ancestorHost = function () { var a = R.ancestorHosts(); return a.length ? a[0] : ""; };
  R.isTop = function () { try { return win.top === win; } catch (e) { return false; } };

  // same-origin child realms reached through contentWindow/contentDocument get the same scriptlets
  function adopt(w) {
    var k;
    try { k = w.Function.prototype; } catch (e) { return; }
    if (!k || apply(wsHas, S.realms, [k]) || !R.M) return;
    if (S.on) installMask(w);
    var cR;
    try { cR = R.M(w, R.SR, SECRET, S); } catch (e) { return; }
    cR.boot(R.run, R.M);
  }
  R.adopt = adopt;
  function hookFrames() {
    if (apply(wsHas, S.hooked, [Fp])) return;
    apply(wsAdd, S.hooked, [Fp]);
    var gW = function (t, th, a) { var v = apply(t, th, a); if (v) adopt(v); return v; };
    var gD = function (t, th, a) {
      var v = apply(t, th, a);
      if (v) { try { var w = apply(n.defaultViewGet, v, []); if (w) adopt(w); } catch (e) { /* ignore */ } }
      return v;
    };
    var ctors = ["HTMLIFrameElement", "HTMLFrameElement", "HTMLObjectElement"];
    for (var i = 0; i < ctors.length; i++) {
      var C = win[ctors[i]];
      if (!C) continue;
      try { R.wrapAccessor(C.prototype, "contentWindow", { get: gW }); } catch (e) { /* ignore */ }
      try { R.wrapAccessor(C.prototype, "contentDocument", { get: gD }); } catch (e) { /* ignore */ }
    }
  }
  // run(R) executes the invocations; M is this factory (kept for child realms)
  R.boot = function (run, M) {
    if (apply(wsHas, S.realms, [Fp])) return;
    apply(wsAdd, S.realms, [Fp]);
    R.run = run; R.M = M;
    try { run(R); } catch (e) { /* ignore */ }
    if (S.on) { ensureMask(); hookFrames(); }
  };
  return R;
}
