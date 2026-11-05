// @world: main
// prevent-canvas: prevent-canvas([contextType]); contextType negatable, empty = every context type.
// Matching getContext() calls return null (the native answer for an unsupported context). Spec 03a 7.3.
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["log", "debug"], 1);
  var P = R.pattern(A.p[0], true);
  var h = function (t, th, a) {
    if (P.test(a.length ? R.str(a[0]) : "")) return null;
    return R.apply(t, th, a);
  };
  var targets = ["HTMLCanvasElement", "OffscreenCanvas"];
  for (var i = 0; i < targets.length; i++) {
    var C = R.win[targets[i]];
    if (typeof C === "function" && C.prototype) R.wrapMethod(C.prototype, "getContext", h);
  }
}
