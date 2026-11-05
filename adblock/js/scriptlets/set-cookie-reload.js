// @deps: set-cookie
// @world: main
// set-cookie-reload: as set-cookie, then reload the page when the cookie value changed. Spec 03c 11.1.
function (R, ...args) {
  R.apply(R.deps["set-cookie"], null, R.apply(R.n.aConcat, [R, { reload: true }], [args]));
}
