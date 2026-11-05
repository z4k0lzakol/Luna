// @deps: lib-json
// @world: main
// evaldata-prune: (prunePaths, [needlePaths]). The object returned by eval() (an object literal evaluated as JSON
// data) is pruned in place with the json-prune paths before eval returns it. Empty prunePaths -> inert.
// Spec 03a 3.3.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 1);
  var prune = R.deps["lib-json"](R).pruner(A.p[0], A.p[1]);
  if (!prune) return;
  R.wrapMethod(R.win, "eval", function (t, th, a) {
    var r = R.apply(t, th, a);
    if (R.isObj(r)) { try { prune(r); } catch (e) { /* ignore */ } }
    return r;
  });
}
