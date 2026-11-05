// @deps: adjust-setTimeout
// @world: main
// adjust-setInterval (nano-setInterval-booster, nano-sib): nano-sib([needle], [delay], [boost]). Spec 03a 4.3.
function (R, ...args) {
  R.apply(R.deps["adjust-setTimeout"], null, R.apply(R.n.aConcat, [R, { target: "setInterval" }], [args]));
}
