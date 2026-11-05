// @deps: edit-element-object
// @world: main
// trusted-edit-element-object: edit-element-object with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-element-object"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
