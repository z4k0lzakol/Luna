// @world: main
// prevent-setTimeout (no-setTimeout-if, nostif, setTimeout-defuser): nostif([needle], [delay]).
// needle and delay ("N", "A-B", "A-", "-B") are both negatable with "!". A defused call still schedules a real
// timer (same delay/args/id semantics) but with a no-op callback. Spec 03a 4.1.
// Internal form (used by prevent-setInterval): first argument {target: "setInterval"}.
function (R, ...args) {
  var target = "setTimeout";
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    if (args[0].target === "setInterval") target = "setInterval";
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 2, ["log", "debug"], 1);
  var needle = A.p[0], delay = A.p[1];
  if (needle === "" && delay === "") return;
  var P = R.pattern(needle, true), D = R.delayMatcher(delay);
  if (!D) return;
  var noop = R.anon(function () {});
  R.wrapMethod(R.win, target, function (t, th, a) {
    var hit = needle === "" ? true : P.test(R.fnText(a[0]));
    if (hit && delay !== "") hit = D(R.delayOf(a[1]));
    if (hit) {
      var b = R.slice(a, 0);
      b[0] = noop;
      return R.apply(t, th, b);
    }
    return R.apply(t, th, a);
  });
}
