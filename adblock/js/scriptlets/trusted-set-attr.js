// @deps: set-attr
// @world: main
// trusted-set-attr (trusted only): (selector, attr, [value]) with any value. Spec 03c 5.
function (R, ...args) {
  R.apply(R.deps["set-attr"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
