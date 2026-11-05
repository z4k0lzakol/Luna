// @deps: edit-outbound-object
// @world: main
// edit-inbound-object: (methodChain, argPos0Based, query); negative position counts from the end. The object argument is edited in place before the call. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-outbound-object"], null, R.apply(R.n.aConcat, [R, { mode: "in" }], [args]));
}
