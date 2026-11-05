// @deps: json-prune-fetch-response
// @world: main
// jsonl-prune-xhr-response: json-prune-xhr-response for JSON Lines bodies (text response types). Spec 03b 7.
function (R, ...args) {
  R.apply(R.deps["json-prune-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true, jsonl: true }], [args]));
}
