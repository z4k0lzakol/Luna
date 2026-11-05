// @deps: lib-json, lib-net
// @world: main
// json-prune: ([prunePaths], [needlePaths], [stackNeedle]); varargs log, logneedle, logstack.
// Prunes (in place, identity kept) the objects returned by JSON.parse and Response.prototype.json (which does not go
// through the page-visible JSON.parse). Paths: legacy syntax a.b.c, [], *, [-], {-} (spec 02 14); every needle
// path must exist first; stackNeedle (negatable) is tested against the normalised stack of the call.
// Empty prunePaths = log-only form -> inert. Spec 03b 6.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["log", "logneedle", "logstack", "debug"], 1);
  var J = R.deps["lib-json"](R), N = R.deps["lib-net"](R);
  var prune = J.pruner(A.p[0], A.p[1]);
  if (!prune) return;
  var SP = A.p[2] !== "" ? R.pattern(A.p[2], true) : null;
  N.onJson(function (obj, stack) {
    if (SP && !SP.test(stack())) return;
    prune(obj);
  });
}
