// @world: main
// trusted-replace-argument (trusted only): (propChain, argpos, value); vararg condition.
// argpos: integer (negative from the end) or "this". value: constant table, json:<JSON>, or
// repl:/regex/replacement/[flags] applied to String(original). Wraps apply and construct. Spec 03a 8.3.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["condition", "log", "debug"], 2);
  var n = R.n, win = R.win;
  var chain = R.trim(A.p[0]), pos = R.trim(A.p[1]), raw = A.p[2];
  if (chain === "" || pos === "") return;
  var isThis = pos === "this", ipos = 0;
  if (!isThis) {
    if (!R.apply(n.reTest, /^-?\d+$/, [pos])) return;
    ipos = n.Number(pos);
  }
  var repl = null, value;
  if (R.startsWith(raw, "repl:")) {
    // repl:/re/replacement/flags  (split at unescaped "/")
    var body = R.slice(raw, 5), segs = [], cur = "", i;
    if (body.charAt(0) !== "/") return;
    for (i = 1; i < body.length; i++) {
      var ch = body.charAt(i);
      if (ch === "\\" && i + 1 < body.length) {
        var nx = body.charAt(i + 1);
        cur += nx === "/" && segs.length === 1 ? "/" : ch + nx;
        i++;
        continue;
      }
      if (ch === "/" && segs.length < 2) { R.push(segs, cur); cur = ""; continue; }
      cur += ch;
    }
    if (segs.length !== 2) return;
    var flags = cur;
    if (!R.apply(n.reTest, /^[dgimsuy]*$/, [flags])) return;
    try { repl = { re: new n.RegExp(segs[0], flags), to: segs[1] }; } catch (e) { return; }
  } else {
    var c = R.constant(raw, false, chain);
    if (!c && R.startsWith(raw, "json:")) {
      try { c = { v: R.apply(n.JSON_parse, win.JSON, [R.slice(raw, 5)]) }; } catch (e) { return; }
    }
    if (!c) return;
    value = c.v;
  }
  var cond = A.x.condition !== undefined && A.x.condition !== "" ? R.pattern(A.x.condition, false) : null;
  var oToString = win.Object.prototype.toString;
  function textOf(v) {
    if (typeof v === "string") return v;
    if (!R.isObj(v)) return R.str(v);
    try { return R.apply(oToString, v, []); } catch (e) { return ""; }
  }
  function newValue(orig) {
    if (!repl) return value;
    repl.re.lastIndex = 0;
    return R.sreplace(textOf(orig), repl.re, repl.to);
  }
  // resolve owner + prop at install time
  var parts = R.split(chain, "."), owner = win;
  for (var k = 0; k < parts.length - 1; k++) {
    if (parts[k] === "") return;
    try { owner = owner[parts[k]]; } catch (e) { return; }
    if (!R.isObj(owner)) return;
  }
  var prop = parts[parts.length - 1];
  if (prop === "") return;
  function edit(th, a) {   // -> [thisArg, args]
    if (isThis) {
      if (cond && !cond.test(textOf(th))) return null;
      return [newValue(th), a];
    }
    var p = ipos < 0 ? a.length + ipos : ipos;
    if (p < 0 || p >= a.length) return null;
    if (cond && !cond.test(textOf(a[p]))) return null;
    var b = R.slice(a, 0);
    b[p] = newValue(a[p]);
    return [th, b];
  }
  R.wrapCtor(owner, prop, function (t, a, nt) {
    var e = isThis ? null : edit(undefined, a);
    return n.construct(t, e ? e[1] : a, nt);
  }, function (t, th, a) {
    var e = edit(th, a);
    return e ? R.apply(t, e[0], e[1]) : R.apply(t, th, a);
  });
}
