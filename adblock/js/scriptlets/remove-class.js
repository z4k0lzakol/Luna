// @deps: remove-attr
// @world: main
// remove-class (rc): rc(names, [selector], [behaviour]); varargs quitAfter, runAt. Spec 03c 4.
function (R, ...args) {
  R.apply(R.deps["remove-attr"], null, R.apply(R.n.aConcat, [R, { cls: true }], [args]));
}
