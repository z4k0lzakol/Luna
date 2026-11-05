// @deps: json-edit-fetch-response
// @world: main
// trusted-json-edit-fetch-request: json-edit-fetch-request with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { trusted: true, request: true }], [args]));
}
