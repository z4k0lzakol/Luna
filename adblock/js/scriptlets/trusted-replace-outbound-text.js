// @world: main
// trusted-replace-outbound-text (trusted-rpot): (methodChain, pattern, [replacement]); varargs condition, encoding.
// The string returned by the method is edited: /re/flags replaces with the regex's own flags, a plain pattern
// replaces every occurrence. replacement "json:<JSON>" is parsed first. encoding "base64": decode before and
// re-encode after. condition: pattern that must be found in the (decoded) text. Spec 03a 8.4.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["condition", "encoding", "log", "debug"], 2);
  var path = R.trim(A.p[0]), pat = A.p[1], rep = A.p[2];
  if (path === "" || pat === "") return;
  var n = R.n, win = R.win;
  if (R.startsWith(rep, "json:")) {
    var jv;
    try { jv = R.apply(n.JSON_parse, win.JSON, [R.slice(rep, 5)]); } catch (e) { return; }
    if (typeof jv === "string") rep = jv;
    else if (jv !== null && typeof jv === "object") rep = R.apply(n.JSON_stringify, win.JSON, [jv]);
    else rep = R.str(jv);
  }
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
  // inherited method: wrap it where it lives (no new own property on `owner`), act only for receivers that are
  // `owner` or inherit from it
  var holder = f.own ? owner : f.holder, isProtoOf = win.Object.prototype.isPrototypeOf;
  function inScope(th) {
    if (holder === owner || th === owner) return true;
    try { return R.apply(isProtoOf, owner, [th]); } catch (e) { return false; }
  }
  var P = R.pattern(pat, false);
  var cond = A.x.condition !== undefined ? A.x.condition : "";
  var COND = cond !== "" ? R.pattern(cond, false) : null;
  var b64 = R.trim(A.x.encoding || "") === "base64";
  R.wrapMethod(holder, prop, function (t, th, a) {
    var r = R.apply(t, th, a);
    if (typeof r !== "string" || !inScope(th)) return r;
    var text = r;
    if (b64) {
      try { text = R.apply(n.atob, win, [r]); } catch (e) { return r; }
    }
    if (COND && !COND.test(text)) return r;
    var out;
    if (P.kind === "regex") {
      P.re.lastIndex = 0;
      out = R.sreplace(text, P.re, rep);
    } else {
      out = R.join(R.split(text, P.text), rep);
    }
    if (out === text) return r;
    if (b64) {
      try { out = R.apply(n.btoa, win, [out]); } catch (e) { return r; }
    }
    return out;
  });
}
