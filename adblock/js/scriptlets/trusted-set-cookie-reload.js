// @deps: set-cookie
// @world: main
// trusted-set-cookie-reload (trusted only): trusted-set-cookie + reload when the value changed. Spec 03c 11.2.
function (R, ...args) {
  R.apply(R.deps["set-cookie"], null, R.apply(R.n.aConcat, [R, { trusted: true, reload: true }], [args]));
}
