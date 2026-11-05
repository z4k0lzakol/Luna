// @deps: set-local-storage-item
// @world: main
// set-session-storage-item: (key, value) on sessionStorage. Spec 03c 12.1.
function (R, ...args) {
  R.apply(R.deps["set-local-storage-item"], null, R.apply(R.n.aConcat, [R, { session: true }], [args]));
}
