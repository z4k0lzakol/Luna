// @deps: lib-json
// @world: main
// edit-outbound-object: (methodChain, query). The method (must exist at install time) is called normally and the
// JSONPath query (json-edit) is applied in place to the object it returned. Spec 03b 9.
// Internal form, first argument {trusted, mode}: mode "in" = edit-inbound-object (methodChain, argPos0Based,
// query; negative = from the end) edits the argument before the call; mode "this" = edit-this-object edits the
// receiver before the call; trusted -> assignments allowed.
function (R, ...args) {
  var o = null;
  if (args.length && args[0] !== null && typeof args[0] === "object") { o = args[0]; args = R.slice(args, 1); }
  o = o || {};
  var mode = o.mode === "in" || o.mode === "this" ? o.mode : "out";
  var A = R.safeArgs(args, mode === "in" ? 3 : 2, ["log", "debug"], mode === "in" ? 3 : 2);
  var J = R.deps["lib-json"](R), n = R.n;
  var own = J.owner(A.p[0]);
  if (!own) return;
  var pos = 0;
  if (mode === "in") {
    if (!R.apply(n.reTest, /^-?\d+$/, [R.trim(A.p[1])])) return;
    pos = n.Number(R.trim(A.p[1]));
  }
  var Q = J.path(A.p[mode === "in" ? 2 : 1], o.trusted === true);
  if (!Q) return;
  R.wrapMethod(own.o, own.p, function (t, th, a) {
    if (mode === "out") {
      var r = R.apply(t, th, a);
      if (R.isObj(r)) { try { Q.run(r); } catch (e) { /* ignore */ } }
      return r;
    }
    if (mode === "this") {
      if (R.isObj(th)) { try { Q.run(th); } catch (e) { /* ignore */ } }
    } else {
      var i = pos < 0 ? a.length + pos : pos;
      if (i >= 0 && i < a.length && R.isObj(a[i])) { try { Q.run(a[i]); } catch (e) { /* ignore */ } }
    }
    return R.apply(t, th, a);
  });
}
