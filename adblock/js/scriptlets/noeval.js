// @world: main
// noeval: no arguments. window.eval becomes a masked wrapper that returns undefined without evaluating anything
// (new Function and string timers are not affected). Nothing is reported (no console). Spec 03a 3.1.
function (R) {
  R.wrapMethod(R.win, "eval", function () { return undefined; });
}
