// @deps: prevent-xhr
// @world: main
// trusted-prevent-xhr: prevent-xhr where an unknown body directive is the literal response text. Spec 03b 5.
function (R, ...args) {
  R.apply(R.deps["prevent-xhr"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
