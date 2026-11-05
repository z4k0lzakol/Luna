// @world: main
// remove-node-text (rmnt): rmnt(nodeName, needle); varargs includes/condition, excludes, sedCount, stay, quitAfter.
// Empties the text of matching nodes. Never writes <script> text (Trusted Types sink): parser-inserted
// scripts are swapped for an empty clone before they run, dynamically inserted ones are retyped around
// the insertion, document.write'd ones are edited in the HTML string. Spec 03c 2.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["includes", "condition", "excludes", "sedCount", "stay", "quitAfter", "log", "debug"], 2);
  var name = R.lower(R.trim(A.p[0])), needle = A.p[1];
  if (name === "" || needle === "") return;
  var n = R.n, doc = R.doc, win = R.win;
  var P = R.pattern(needle, false);
  var inc = A.x.includes !== undefined ? A.x.includes : A.x.condition;
  var INC = inc !== undefined && inc !== "" ? R.pattern(inc, false) : null;
  var EXC = A.x.excludes !== undefined && A.x.excludes !== "" ? R.pattern(A.x.excludes, false) : null;
  var sedCount = R.n.Number(A.x.sedCount || "0");
  if (sedCount !== sedCount || sedCount < 0) sedCount = 0;
  var stay = A.x.stay !== undefined && A.x.stay !== "0";
  var quitAfter = R.n.Number(A.x.quitAfter || "0");
  if (quitAfter !== quitAfter || quitAfter < 0) quitAfter = 0;
  var isText = name === "#text", isScriptName = name === "script";
  var count = 0, done = false, stops = [];

  function qualifies(t) {
    return t !== "" && P.test(t) && (!INC || INC.test(t)) && (!EXC || !EXC.test(t));
  }
  function counted() {
    count++;
    if (sedCount && count >= sedCount) stop();
  }
  function handle(nd) {
    if (done) return;
    var t = R.text(nd);
    if (!qualifies(t)) return;
    if (R.isScript(nd)) {
      if (!R.emptyScript(nd)) return;
    } else if (R.nodeType(nd) === 3 && R.isScript(R.parent(nd))) {
      if (!R.emptyScript(R.parent(nd))) return;
    } else if (!R.setText(nd, "")) {
      return;
    }
    counted();
  }
  function nameOK(nd) {
    return R.lower(R.nodeName(nd)) === name;
  }
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
          // text arriving into a parser-inserted <script> (network chunks)
          var p = R.parent(nd);
          if (R.isScript(p)) handle(p);
          continue;
        }
        scan(nd);
      }
    }
  }
  stops[stops.length] = R.observe(doc, { childList: true, subtree: true, characterData: isText || isScriptName }, onMut);
  if (isScriptName) {
    stops[stops.length] = R.onScriptInsert(function (el) {
      if (done) return false;
      if (!qualifies(R.text(el))) return false;
      counted();
      return true;
    });
    var RE_SCRIPT = /(<script\b[^>]*>)([\s\S]*?)(<\/script\s*>)/gi;
    stops[stops.length] = R.onWrite(function (html) {
      if (done) return html;
      return R.sreplace(html, RE_SCRIPT, function (m, open, body, close) {
        if (done || !qualifies(body)) return m;
        counted();
        return open + close;
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
