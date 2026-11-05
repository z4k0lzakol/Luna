// @world: main
// noeval-if (prevent-eval-if): (needle). eval(code) with a string code matching needle (pattern) returns undefined;
// everything else is forwarded to the native eval (as with any eval wrapper, direct eval becomes indirect).
// Empty needle = log-only form -> inert. Spec 03a 3.2.
function (R, ...args) {
  var needle = R.str(args[0]);
  if (needle === "") return;
  var P = R.pattern(needle, false);
  R.wrapMethod(R.win, "eval", function (t, th, a) {
    if (typeof a[0] === "string" && P.test(a[0])) return undefined;
    return R.apply(t, th, a);
  });
}
