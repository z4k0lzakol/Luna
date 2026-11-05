// @deps: set-constant
// @world: main
// trusted-set-constant (trusted-set): set-constant with the trusted value parser (json:..., {"value": ...},
// raw strings, integers outside -32767..32767) and without the install-time type guard. Spec 03a 3.6.
function (R, ...args) {
  R.apply(R.deps["set-constant"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
