// @world: main
// trusted-suppress-native-method: (methodPath, signature, [how], [stack]). Spec 03a 8.1.
// signature: "|"-separated matchers, one per argument position (blank = any). Each matcher is JSON-parsed if
// possible: string -> pattern (substring or /re/), number/boolean/null -> strict equality, array -> all elements
// contained in the argument array, object -> every key strictly equal on the argument; otherwise a raw pattern.
// how: "abort" (default, silent ReferenceError) | "prevent" (return undefined) | "debug" (inert).
// stack: pattern on the normalised stack, "!" negates. Constructors (Function) are wrapped with construct too.
function (R, ...args) {
  var A = R.safeArgs(args, 4, [], 4);
  var path = R.trim(A.p[0]), sig = A.p[1], how = R.trim(A.p[2]);
  if (how === "") how = "abort";
  if (path === "" || R.trim(sig) === "") return;
  if (how !== "abort" && how !== "prevent") return;
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
  // inherited method: wrap it where it lives (no new own property on `owner`) and only act for receivers that
  // are `owner` or inherit from it
  var holder = f.own ? owner : f.holder, isProtoOf = win.Object.prototype.isPrototypeOf;
  function inScope(th) {
    if (holder === owner || th === owner) return true;
    try { return R.apply(isProtoOf, owner, [th]); } catch (e) { return false; }
  }
  var objToString = win.Object.prototype.toString;
  function argText(a) {
    var t = typeof a;
    if (t === "string") return a;
    if (a === null || (t !== "object" && t !== "function")) return R.str(a);
    try { return R.apply(objToString, a, []); } catch (e) { return ""; }
  }
  function isPrim(v) { return v === null || (typeof v !== "object" && typeof v !== "function"); }
  function matcher(m) {
    if (R.trim(m) === "") return null;
    var v, ok = true;
    try { v = R.apply(n.JSON_parse, win.JSON, [m]); } catch (e) { ok = false; }
    if (ok) {
      if (typeof v === "string") {
        var P = R.pattern(v, false);
        return function (a) { return P.test(argText(a)); };
      }
      if (isPrim(v)) return function (a) { return a === v; };
      if (n.isArray(v)) {
        return function (a) {
          if (!n.isArray(a)) return false;
          for (var k = 0; k < v.length; k++) {
            var found = false;
            for (var j = 0; j < a.length && !found; j++) found = a[j] === v[k];
            if (!found) return false;
          }
          return true;
        };
      }
      var keys = n.keys(v);
      return function (a) {
        if (!R.isObj(a)) return false;
        for (var k = 0; k < keys.length; k++) {
          var x = v[keys[k]];
          if (!isPrim(x) || a[keys[k]] !== x) return false;
        }
        return true;
      };
    }
    var Q = R.pattern(m, false);
    return function (a) { return Q.test(argText(a)); };
  }
  var raw = R.split(sig, "|"), M = [];
  for (i = 0; i < raw.length; i++) M[i] = matcher(raw[i]);
  var SP = A.p[3] !== "" ? R.pattern(A.p[3], true) : null;
  var msg = R.abortMsg(path), busy = false;
  // "prevent" on the Function constructor (anti-devtools `x.constructor("debugger")`): hand back an empty function
  // instead of undefined/constructing one (constructing would hit the page's CSP unsafe-eval check)
  var isFn = f.desc.value === win.Function;
  var empty = function () { return R.fn(R.anon(function () {}), "function anonymous(\n) {\n\n}"); };
  function hit(a, above) {
    if (busy) return false;
    busy = true;
    try {
      for (var k = 0; k < M.length; k++) {
        if (M[k] !== null && !M[k](a[k])) return false;
      }
      return !SP || SP.test(R.stack(above));
    } catch (e) {
      return false;
    } finally {
      busy = false;
    }
  }
  var H = {
    apply: function (t, th, a) {
      if (inScope(th) && hit(a, H.apply)) {
        if (how === "prevent") return isFn ? empty() : undefined;
        R.abort(msg, H.apply);
      }
      return R.apply(t, th, a);
    },
    construct: function (t, a, nt) {
      if (hit(a, H.construct)) {
        if (how === "prevent") return isFn ? empty() : n.construct(t, [], nt);
        R.abort(msg, H.construct);
      }
      return n.construct(t, a, nt);
    }
  };
  var px = R.proxy(f.desc.value, H);
  R.redefine(holder, prop, px);
}
