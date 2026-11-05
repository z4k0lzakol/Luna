// @world: main
// trusted-override-element-method: (methodPath, [selector], [disposition]). Spec 03a 8.2.
// Calls on an Element receiver matching selector (empty = any element) are replaced: disposition "" -> return
// undefined, "throw" -> silent ReferenceError, "debug" -> inert, else the untrusted constant value.
function (R, ...args) {
  var A = R.safeArgs(args, 3, [], 3);
  var path = R.trim(A.p[0]), sel = R.trim(A.p[1]), disp = R.trim(A.p[2]);
  if (path === "" || disp === "debug") return;
  var n = R.n, win = R.win;
  var parts = R.split(path, "."), owner = win, i;
  for (i = 0; i < parts.length - 1; i++) {
    if (parts[i] === "") return;
    try { owner = owner[parts[i]]; } catch (e) { return; }
    if (!R.isObj(owner)) return;
  }
  var prop = parts[parts.length - 1];
  if (prop === "") return;
  var f = R.findDesc(owner, prop);
  if (!f || typeof f.desc.value !== "function") return;
  // an inherited method is wrapped where it lives (no new own property on `owner`, e.g.
  // HTMLAnchorElement.prototype.click lives on HTMLElement.prototype); only receivers that are `owner` or inherit
  // from it are affected
  var holder = f.own ? owner : f.holder, isProtoOf = win.Object.prototype.isPrototypeOf;
  function inScope(th) {
    if (holder === owner || th === owner) return true;
    try { return R.apply(isProtoOf, owner, [th]); } catch (e) { return false; }
  }
  if (sel !== "") {
    try { R.apply(n.querySelector, R.doc, [sel]); } catch (e) { return; }
  }
  var c = null;
  if (disp !== "" && disp !== "throw") {
    c = R.constant(disp, false, path);
    if (!c) return;
  }
  var msg = R.abortMsg(path);
  var H = {
    apply: function (t, th, a) {
      if (R.nodeType(th) !== 1 || !inScope(th)) return R.apply(t, th, a);
      if (sel !== "") {
        var ok = false;
        try { ok = R.apply(n.matches, th, [sel]); } catch (e) { ok = false; }
        if (!ok) return R.apply(t, th, a);
      }
      if (disp === "throw") R.abort(msg, H.apply);
      return c ? c.v : undefined;
    }
  };
  R.wrapMethod(holder, prop, H.apply);
}
