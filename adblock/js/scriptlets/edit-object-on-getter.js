// @deps: edit-object-on-setter
// @world: main
// edit-object-on-getter: (chain, query). The value read from the property at chain is edited in place before it is returned. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["edit-object-on-setter"], null, R.apply(R.n.aConcat, [R, { getter: true }], [args]));
}
