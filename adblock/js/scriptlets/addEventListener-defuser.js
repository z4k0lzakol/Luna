// @world: main
// addEventListener-defuser (aeld, prevent-addEventListener): aeld([type], [handlerNeedle]);
// varargs runAt, elements. type: plain = exact event name, /re/ = regex. handlerNeedle: pattern on the
// handler source (handleEvent for listener objects). Matching calls are not registered. Spec 03a 5.1.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["runAt", "elements", "debug", "log"], 1);
  var type = A.p[0], hn = A.p[1];
  if (type === "" && hn === "") return;
  var n = R.n, win = R.win, doc = R.doc;
  var TP = R.exactPattern(type), HP = R.pattern(hn, false);
  var sel = A.x.elements !== undefined ? R.trim(A.x.elements) : "";
  if (sel !== "" && sel !== "window" && sel !== "document") {
    try { R.apply(n.querySelector, doc, [sel]); } catch (e) { return; }
  }
  function elementsOK(th) {
    if (sel === "") return true;
    var tgt = (th === undefined || th === null) ? win : th;
    if (sel === "window") return tgt === win;
    if (sel === "document") return tgt === doc;
    if (R.nodeType(tgt) !== 1) return false;
    try { return R.apply(n.matches, tgt, [sel]); } catch (e) { return false; }
  }
  function handlerText(cb) {
    if (typeof cb === "function") return R.fnText(cb);
    if (cb !== null && typeof cb === "object") {
      var he;
      try { he = cb.handleEvent; } catch (e) { return ""; }
      return typeof he === "function" ? R.fnText(he) : "";
    }
    return "";
  }
  var install = function () {
    R.wrapMethod(win.EventTarget.prototype, "addEventListener", function (t, th, a) {
      if (a.length >= 2) {
        if (type !== "" && !TP.test(R.str(a[0]))) return R.apply(t, th, a);
        if (hn !== "" && !HP.test(handlerText(a[1]))) return R.apply(t, th, a);
        if (!elementsOK(th)) return R.apply(t, th, a);
        return undefined;
      }
      return R.apply(t, th, a);
    });
  };
  R.onReady(install, A.x.runAt);
}
