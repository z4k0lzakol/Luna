// @world: main
// trusted-click-element (trusted only): (directives, [extraMatch], [delayMs], [reloadAfterClick[:ms]],
// [observerTimeoutSec]). directives: comma-separated (top-level commas only), each an integer (wait ms),
// "xpath:EXPR", "when-visible:SEL" or a CSS selector where "A >>> B" pierces open shadow roots.
// extraMatch: comma-separated cookie:NAME[=VALUE], localStorage:KEY[=VALUE] (NAME/VALUE are patterns, "!" prefix
// = must not exist), containsText:TEXT (AdGuard; clickType ignored). Mutation-driven (no polling), gives up after
// 10 s (or observerTimeoutSec). Spec 03c 10.
function (R, ...args) {
  var A = R.safeArgs(args, 5, ["log", "debug"], 1);
  var n = R.n, win = R.win, doc = R.doc;
  var raw = R.trim(A.p[0]);
  if (raw === "") return;
  // ---- split directives on top-level commas
  function splitTop(s) {
    var out = [], cur = "", depth = 0, q = "";
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      if (q) { if (c === "\\" && i + 1 < s.length) { cur += c + s.charAt(++i); continue; } if (c === q) q = ""; cur += c; continue; }
      if (c === '"' || c === "'") { q = c; cur += c; continue; }
      if (c === "(" || c === "[") depth++;
      else if ((c === ")" || c === "]") && depth > 0) depth--;
      else if (c === "\\" && s.charAt(i + 1) === ",") { cur += ","; i++; continue; }
      else if (c === "," && depth === 0) { R.push(out, R.trim(cur)); cur = ""; continue; }
      cur += c;
    }
    R.push(out, R.trim(cur));
    return out;
  }
  var dirs = [], parts = splitTop(raw);
  for (var i = 0; i < parts.length; i++) {
    var d = parts[i];
    if (d === "") continue;
    if (R.apply(n.reTest, /^\d+$/, [d])) { R.push(dirs, { wait: n.Number(d) }); continue; }
    var vis = false;
    if (R.startsWith(d, "when-visible:")) { vis = true; d = R.trim(R.slice(d, 13)); }
    if (R.startsWith(d, "xpath:")) { R.push(dirs, { xpath: R.slice(d, 6), vis: vis }); continue; }
    var segs = R.split(d, ">>>"), sel = [];
    for (var s = 0; s < segs.length; s++) {
      var sg = R.trim(segs[s]);
      if (sg === "") { sel = null; break; }
      try { R.apply(n.querySelector, doc, [sg]); } catch (e) { sel = null; break; }
      R.push(sel, sg);
    }
    if (!sel) return;   // invalid selector -> inert
    R.push(dirs, { sel: sel, vis: vis });
  }
  if (!dirs.length) return;
  // ---- extra conditions
  var conds = [], containsText = null;
  var extra = R.trim(A.p[1]);
  if (extra !== "") {
    var cl = splitTop(extra);
    for (var c = 0; c < cl.length; c++) {
      var x = cl[c], neg = false;
      if (x === "") continue;
      if (x.charAt(0) === "!") { neg = true; x = R.slice(x, 1); }
      var m = R.apply(n.reExec, /^(cookie|localStorage|containsText|clickType):([\s\S]*)$/, [x]);
      if (!m) return;   // unknown condition -> inert
      if (m[1] === "containsText") { containsText = m[2]; continue; }
      if (m[1] === "clickType") continue;
      var body = m[2], eq = R.indexOf(body, "=");
      var nameP = R.pattern(eq === -1 ? body : R.slice(body, 0, eq), false);
      var valP = eq === -1 ? null : R.pattern(R.slice(body, eq + 1), false);
      R.push(conds, { kind: m[1], neg: neg, name: nameP, value: valP });
    }
  }
  var delay = A.p[2] === "" ? 0 : n.Number(A.p[2]);
  if (delay !== delay || delay < 0) delay = 0;
  var reloadMs = -1;
  var rl = R.trim(A.p[3]);
  if (rl !== "") {
    var mr = R.apply(n.reExec, /^reloadAfterClick(?::(\d+))?$/, [rl]);
    if (mr) reloadMs = mr[1] !== undefined ? n.Number(mr[1]) : 500;
  }
  var timeout = 10000;
  if (A.p[4] !== "") { var ts = n.Number(A.p[4]); if (ts === ts && ts > 0) timeout = ts * 1000; }
  // ---- natives
  var HE = win.HTMLElement.prototype, clickFn = HE.click;
  var shadowGet = n.getOwnPropertyDescriptor(win.Element.prototype, "shadowRoot").get;
  var srQS = win.ShadowRoot ? win.ShadowRoot.prototype.querySelector : null;
  var srQSA = win.ShadowRoot ? win.ShadowRoot.prototype.querySelectorAll : null;
  var evaluate = win.Document.prototype.evaluate;
  var singleGet = win.XPathResult ? n.getOwnPropertyDescriptor(win.XPathResult.prototype, "singleNodeValue").get : null;
  var checkVis = win.Element.prototype.checkVisibility;
  var ME = win.MouseEvent, dispatch = n.dispatchEvent;
  var IO = win.IntersectionObserver, ioObserve = IO ? IO.prototype.observe : null, ioDisc = IO ? IO.prototype.disconnect : null;
  var lsGetter = R.findDesc(win, "localStorage");
  var SP = win.Storage ? win.Storage.prototype : null;
  var stGetItem = SP ? SP.getItem : null, stKey = SP ? SP.key : null;
  var stLen = SP ? n.getOwnPropertyDescriptor(SP, "length").get : null;
  var reload = win.location.reload;

  function cookiesOK() {
    for (var i = 0; i < conds.length; i++) {
      var cd = conds[i], found = false;
      if (cd.kind === "cookie") {
        var all = "";
        try { all = R.str(R.apply(n.cookieGet, doc, [])); } catch (e) { all = ""; }
        var ps = R.split(all, ";");
        for (var j = 0; j < ps.length && !found; j++) {
          var p = R.trim(ps[j]);
          if (p === "") continue;
          var k = R.indexOf(p, "=");
          var nm = k === -1 ? p : R.slice(p, 0, k), vl = k === -1 ? "" : R.slice(p, k + 1);
          if (cd.name.test(nm) && (!cd.value || cd.value.test(vl))) found = true;
        }
      } else {
        try {
          var st = lsGetter && lsGetter.desc.get ? R.apply(lsGetter.desc.get, win, []) : null;
          if (st) {
            var len = R.apply(stLen, st, []);
            for (var q = 0; q < len && !found; q++) {
              var key = R.apply(stKey, st, [q]);
              if (key === null || !cd.name.test(key)) continue;
              var v = R.apply(stGetItem, st, [key]);
              if (!cd.value || cd.value.test(R.str(v))) found = true;
            }
          }
        } catch (e) { found = false; }
      }
      if (found === cd.neg) return false;
    }
    return true;
  }
  function textOK(el) {
    return containsText === null || R.includes(R.text(el), containsText);
  }
  function lookup(dr) {
    if (dr.xpath !== undefined) {
      try {
        var res = R.apply(evaluate, doc, [dr.xpath, doc, null, 9, null]);
        var nd = R.apply(singleGet, res, []);
        return nd && textOK(nd) ? nd : null;
      } catch (e) { return null; }
    }
    var root = doc;
    for (var i = 0; i < dr.sel.length; i++) {
      var last = i === dr.sel.length - 1;
      if (last && containsText !== null) {
        var l;
        try {
          l = R.toArray(root === doc ? R.apply(n.querySelectorAll, doc, [dr.sel[i]]) : R.apply(srQSA, root, [dr.sel[i]]));
        } catch (e) { return null; }
        for (var j = 0; j < l.length; j++) if (textOK(l[j])) return l[j];
        return null;
      }
      var el;
      try { el = root === doc ? R.apply(n.querySelector, doc, [dr.sel[i]]) : R.apply(srQS, root, [dr.sel[i]]); }
      catch (e) { return null; }
      if (!el) return null;
      if (last) return el;
      try { root = R.apply(shadowGet, el, []); } catch (e) { return null; }
      if (!root) return null;
    }
    return null;
  }
  function visible(el) {
    try {
      if (typeof checkVis === "function" && !R.apply(checkVis, el, [{ opacityProperty: true, visibilityProperty: true }])) return false;
      var r = R.apply(n.getBoundingClientRect, el, []);
      return r.width > 0 && r.height > 0;
    } catch (e) { return false; }
  }
  function click(el) {
    try {   // native HTMLElement.prototype.click (throws for non-HTML elements such as <svg> -> dispatch)
      if (typeof clickFn === "function") { R.apply(clickFn, el, []); return; }
    } catch (e) { /* fall through */ }
    try { R.apply(dispatch, el, [new ME("click", { bubbles: true, cancelable: true, view: win })]); } catch (e) { /* ignore */ }
  }
  // ---- state machine
  var idx = 0, finished = false, unobserve = null, io = null, deadline = 0, waiting = false;
  function finish() {
    finished = true;
    if (unobserve) { unobserve(); unobserve = null; }
    if (io) { try { R.apply(ioDisc, io, []); } catch (e) { /* ignore */ } io = null; }
  }
  function step() {
    if (finished || waiting) return;
    while (idx < dirs.length) {
      if (R.now() > deadline) { finish(); return; }
      var dr = dirs[idx];
      if (dr.wait !== undefined) {
        idx++;
        waiting = true;
        R.later(function () { waiting = false; step(); }, dr.wait);
        return;
      }
      var el = lookup(dr);
      if (!el) { watch(); return; }
      if (dr.vis && !visible(el)) { watch(el); return; }
      if (io) { try { R.apply(ioDisc, io, []); } catch (e) { /* ignore */ } io = null; }
      click(el);
      idx++;
    }
    finish();
    if (reloadMs >= 0) R.later(function () { try { R.apply(reload, win.location, []); } catch (e) { /* ignore */ } }, reloadMs);
  }
  function watch(el) {
    if (!unobserve) {
      unobserve = R.observe(doc, { childList: true, subtree: true, attributes: true }, function () { step(); });
    }
    if (el && IO && !io) {
      try {
        io = new IO(function () { step(); }, { threshold: [0, 0.01] });
        R.apply(ioObserve, io, [el]);
      } catch (e) { io = null; }
    }
  }
  function begin() {
    if (!cookiesOK()) return;
    deadline = R.now() + timeout;
    R.later(function () { if (!finished) finish(); }, timeout + 50);
    step();
  }
  if (delay > 0) R.later(begin, delay);
  else begin();
}
