// @deps: edit-object-on-setter
// @world: main
// trusted-edit-object-on-setter: edit-object-on-setter with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-object-on-setter"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
