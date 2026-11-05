// @deps: prevent-fetch
// @world: main
// trusted-prevent-fetch: prevent-fetch where an unknown body directive is the literal response text and the
// response config may set headers / any statusText. Spec 03b 3.
function (R, ...args) {
  R.apply(R.deps["prevent-fetch"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
