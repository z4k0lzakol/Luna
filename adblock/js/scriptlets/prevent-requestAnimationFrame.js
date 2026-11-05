// @world: main
// prevent-requestAnimationFrame (no-requestAnimationFrame-if, norafif): norafif(needle); needle negatable.
// A defused call still requests a real frame (real id, cancelAnimationFrame works) with a no-op callback.
// Spec 03a 4.4.
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["log", "debug"], 1);
  var needle = A.p[0];
  if (needle === "") return;
  var P = R.pattern(needle, true);
  var noop = R.anon(function () {});
  R.wrapMethod(R.win, "requestAnimationFrame", function (t, th, a) {
    if (a.length && P.test(R.fnText(a[0]))) {
      var b = R.slice(a, 0);
      b[0] = noop;
      return R.apply(t, th, b);
    }
    return R.apply(t, th, a);
  });
}
