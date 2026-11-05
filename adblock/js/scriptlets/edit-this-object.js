// @deps: edit-outbound-object
// @world: main
// edit-this-object: (methodChain, query). The receiver (this) is edited in place before the call. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-outbound-object"], null, R.apply(R.n.aConcat, [R, { mode: "this" }], [args]));
}
