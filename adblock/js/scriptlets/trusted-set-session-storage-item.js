// @deps: set-local-storage-item
// @world: main
// trusted-set-session-storage-item (trusted only): as trusted-set-local-storage-item on sessionStorage.
// Spec 03c 12.2.
function (R, ...args) {
  R.apply(R.deps["set-local-storage-item"], null, R.apply(R.n.aConcat, [R, { trusted: true, session: true }], [args]));
}
