// @deps: lib-json
// @world: main
// trusted-prune-outbound-object: (methodChain, prunePaths, [needlePaths]); vararg stackToMatch.
// The method (must exist at install time) is called normally, then the object it returned is pruned in place.
// Spec 03b 8.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["stackToMatch", "log", "debug"], 2);
  var J = R.deps["lib-json"](R);
  var own = J.owner(A.p[0]);
  if (!own) return;
  var prune = J.pruner(A.p[1], A.p[2]);
  if (!prune) return;
  var SP = A.x.stackToMatch !== undefined && A.x.stackToMatch !== "" ? R.pattern(A.x.stackToMatch, true) : null;
  var h = function (t, th, a) {
    var r = R.apply(t, th, a);
    if (R.isObj(r) && (!SP || SP.test(R.stack(h)))) { try { prune(r); } catch (e) { /* ignore */ } }
    return r;
  };
  R.wrapMethod(own.o, own.p, h);
}
