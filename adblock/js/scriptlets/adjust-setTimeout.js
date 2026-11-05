// @world: main
// adjust-setTimeout (nano-setTimeout-booster, nano-stb): nano-stb([needle], [delay], [boost]).
// needle: pattern (default all); delay: exact ms (default 1000) or "*"; boost: factor clamped to 0.001..50
// (default 0.05). Matching calls get delay * boost. Spec 03a 4.3.
// Internal form (used by adjust-setInterval): first argument {target: "setInterval"}.
function (R, ...args) {
  var target = "setTimeout";
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    if (args[0].target === "setInterval") target = "setInterval";
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 3, [], 3);
  var P = R.pattern(A.p[0], false);
  var ds = R.trim(A.p[1]), any = ds === "*", delay = 1000;
  if (!any && ds !== "") {
    delay = R.n.Number(ds);
    if (delay !== delay) return;
  }
  var bs = R.trim(A.p[2]), boost = 0.05;
  if (bs !== "") {
    boost = R.n.Number(bs);
    if (boost !== boost) boost = 0.05;
  }
  if (boost < 0.001) boost = 0.001;
  if (boost > 50) boost = 50;
  R.wrapMethod(R.win, target, function (t, th, a) {
    if (a.length) {
      var d = R.delayOf(a[1]);
      if ((any || d === delay) && (P.kind === "all" || P.test(R.fnText(a[0])))) {
        var b = R.slice(a, 0);
        b[1] = d * boost;
        if (b.length < 2) b.length = 2;
        return R.apply(t, th, b);
      }
    }
    return R.apply(t, th, a);
  });
}
