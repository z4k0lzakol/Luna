// @deps: edit-outbound-object
// @world: main
// trusted-edit-outbound-object: edit-outbound-object with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-outbound-object"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
