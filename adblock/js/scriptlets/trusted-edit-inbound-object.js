// @deps: edit-outbound-object
// @world: main
// trusted-edit-inbound-object: edit-inbound-object with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-outbound-object"], null, R.apply(R.n.aConcat, [R, { trusted: true, mode: "in" }], [args]));
}
