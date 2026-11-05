// @world: main
// trusted-replace-node-text (trusted-rpnt, replace-node-text, rpnt; trusted only):
// rpnt(nodeName, pattern, [replacement]); varargs includes/condition, excludes, sedCount, stay, quitAfter.
// Regex patterns use their own flags ($1 references work); plain patterns replace every occurrence.
// <script> text is written only as a TrustedScript from the runtime's lazy policy (no Trusted Types
// violation); parser-inserted scripts are edited from a MutationObserver before they run, dynamically
// inserted ones right before insertion, document.write'd ones in the HTML string. Spec 03c 3.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["includes", "condition", "excludes", "sedCount", "stay", "quitAfter", "log", "debug"], 2);
  var name = R.lower(R.trim(A.p[0])), pattern = A.p[1], replacement = A.p[2];
  if (name === "" || pattern === "") return;
  var n = R.n, doc = R.doc, win = R.win;
  var P = R.pattern(pattern, false);
  var inc = A.x.includes !== undefined ? A.x.includes : A.x.condition;
  var INC = inc !== undefined && inc !== "" ? R.pattern(inc, false) : null;
  var EXC = A.x.excludes !== undefined && A.x.excludes !== "" ? R.pattern(A.x.excludes, false) : null;
  var sedCount = n.Number(A.x.sedCount || "0");
  if (sedCount !== sedCount || sedCount < 0) sedCount = 0;
  var stay = A.x.stay !== undefined && A.x.stay !== "0";
  var quitAfter = n.Number(A.x.quitAfter || "0");
  if (quitAfter !== quitAfter || quitAfter < 0) quitAfter = 0;
  var isText = name === "#text", isScriptName = name === "script";
  var count = 0, done = false, stops = [];
  var scriptTextSet = n.getOwnPropertyDescriptor(n.HTMLScriptElement.prototype, "text").set;
  var WM = n.WeakMap, wmGet = WM.prototype.get, wmSet = WM.prototype.set, written = new WM();

  function replaceIn(t) {
    if (P.kind === "regex") { P.re.lastIndex = 0; return R.sreplace(t, P.re, replacement); }
    return R.join(R.split(t, P.text), replacement);
  }
  function edited(t) {   // -> new text or null when the node does not qualify / nothing changes
    if (t === "" || !P.test(t) || (INC && !INC.test(t)) || (EXC && EXC.test(t))) return null;
    var nt = replaceIn(t);
    return nt === t ? null : nt;
  }
  function counted() {
    count++;
    if (sedCount && count >= sedCount) stop();
  }
  function writeScript(el, t) {
    var v = R.trusted("script", t);
    if (v === null) return false;
    try { R.apply(scriptTextSet, el, [v]); } catch (e) { return false; }
    R.apply(wmSet, written, [el, t]);
    return true;
  }
  function handle(nd) {
    if (done) return;
    if (R.nodeType(nd) === 3 && R.isScript(R.parent(nd))) nd = R.parent(nd);
    var t = R.text(nd);
    if (R.apply(wmGet, written, [nd]) === t) return;   // our own write
    var nt = edited(t);
    if (nt === null) return;
    if (R.isScript(nd)) {
      if (!writeScript(nd, nt)) return;
    } else {
      if (!R.setText(nd, nt)) return;
      R.apply(wmSet, written, [nd, nt]);
    }
    counted();
  }
  function nameOK(nd) { return R.lower(R.nodeName(nd)) === name; }
  function scan(root) {
    var t = R.nodeType(root);
    if (isText) {
      if (t === 3) { handle(root); return; }
      if (t !== 1 && t !== 9 && t !== 11) return;
      var tw;
      try { tw = R.apply(n.createTreeWalker, doc, [root, 4]); } catch (e) { return; }
      var list = [], x;
      while ((x = R.apply(n.twNext, tw, []))) list[list.length] = x;
      for (var i = 0; i < list.length; i++) handle(list[i]);
      return;
    }
    if (t === 1 && nameOK(root)) handle(root);
    if (t === 1 || t === 9 || t === 11) {
      var l;
      try {
        l = R.apply(t === 1 ? n.elQuerySelectorAll : t === 9 ? n.querySelectorAll : n.fragQuerySelectorAll, root, [name]);
      } catch (e) { return; }
      var arr = R.toArray(l);
      for (var j = 0; j < arr.length; j++) handle(arr[j]);
    }
  }
  function onMut(recs) {
    for (var i = 0; i < recs.length && !done; i++) {
      var r = recs[i];
      if (r.type === "characterData") {
        if (isText) handle(r.target);
        else if (isScriptName && R.isScript(R.parent(r.target))) handle(R.parent(r.target));
        continue;
      }
      var added = r.addedNodes;
      for (var j = 0; j < added.length && !done; j++) {
        var nd = added[j];
        if (isScriptName && R.nodeType(nd) === 3) {
          if (R.isScript(R.parent(nd))) handle(R.parent(nd));
          continue;
        }
        scan(nd);
      }
    }
  }
  stops[stops.length] = R.observe(doc, { childList: true, subtree: true, characterData: isText || isScriptName }, onMut);
  if (isScriptName) {
    stops[stops.length] = R.onScriptInsert(function (el) {
      if (!done) handle(el);
      return false;
    });
    var RE_SCRIPT = /(<script\b[^>]*>)([\s\S]*?)(<\/script\s*>)/gi;
    stops[stops.length] = R.onWrite(function (html) {
      if (done) return html;
      return R.sreplace(html, RE_SCRIPT, function (m, open, body, close) {
        if (done) return m;
        var nt = edited(body);
        if (nt === null) return m;
        counted();
        return open + nt + close;
      });
    });
  }
  function stop() {
    if (done) return;
    done = true;
    for (var i = 0; i < stops.length; i++) { try { stops[i](); } catch (e) { /* ignore */ } }
  }
  scan(doc);
  if (!stay) {
    if (quitAfter > 0) R.onReady(function () { R.later(stop, quitAfter); }, "interactive");
    else if (!sedCount) R.onReady(stop, "interactive");
  }
}
