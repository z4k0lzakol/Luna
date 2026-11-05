// @deps: json-edit-fetch-response
// @world: main
// trusted-jsonl-edit-xhr-response: jsonl-edit-xhr-response with assignments. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { trusted: true, xhr: true, jsonl: true }], [args]));
}
