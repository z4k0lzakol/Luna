// @deps: prevent-setTimeout
// @world: main
// prevent-setInterval (no-setInterval-if, nosiif, setInterval-defuser): nosiif([needle], [delay]). Spec 03a 4.1.
function (R, ...args) {
  R.apply(R.deps["prevent-setTimeout"], null, R.apply(R.n.aConcat, [R, { target: "setInterval" }], [args]));
}
