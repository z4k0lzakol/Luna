// @deps: lib-json
// @world: main
// trusted-prune-inbound-object: (methodChain, argPos1Based, prunePaths, [needlePaths]); varargs dontOverwrite,
// stackToMatch. The method must exist at install time. Before the call, the object argument at argPos (1-based)
// is pruned in place, or (dontOverwrite) a structured clone of it is pruned and passed instead. Spec 03b 8.
function (R, ...args) {
  var A = R.safeArgs(args, 4, ["dontOverwrite", "stackToMatch", "log", "debug"], 3);
  var J = R.deps["lib-json"](R), n = R.n;
  var own = J.owner(A.p[0]);
  if (!own) return;
  if (!R.apply(n.reTest, /^\d+$/, [A.p[1]])) return;
  var pos = n.Number(A.p[1]) - 1;
  if (pos < 0) return;
  var prune = J.pruner(A.p[2], A.p[3]);
  if (!prune) return;
  var keep = A.x.dontOverwrite !== undefined && A.x.dontOverwrite !== "" && A.x.dontOverwrite !== "0" &&
    A.x.dontOverwrite !== "false";
  var SP = A.x.stackToMatch !== undefined && A.x.stackToMatch !== "" ? R.pattern(A.x.stackToMatch, true) : null;
  var sclone = R.win.structuredClone;
  var h = function (t, th, a) {
    if (pos < a.length && R.isObj(a[pos]) && (!SP || SP.test(R.stack(h)))) {
      if (keep) {
        var c;
        try { c = R.apply(sclone, R.win, [a[pos]]); } catch (e) { c = undefined; }
        if (R.isObj(c) && prune(c)) { var b = R.slice(a, 0); b[pos] = c; return R.apply(t, th, b); }
      } else {
        try { prune(a[pos]); } catch (e) { /* ignore */ }
      }
    }
    return R.apply(t, th, a);
  };
  R.wrapMethod(own.o, own.p, h);
}
