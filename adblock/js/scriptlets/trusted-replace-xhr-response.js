// @deps: trusted-replace-fetch-response
// @world: main
// trusted-replace-xhr-response: trusted-replace-fetch-response for XHR (responseType ""/"text"; "json" is edited on
// the serialised JSON and re-parsed, a parse failure leaves it untouched). Spec 03b 12.
function (R, ...args) {
  R.apply(R.deps["trusted-replace-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true }], [args]));
}
