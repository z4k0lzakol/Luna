// @deps: json-prune-fetch-response
// @world: main
// jsonl-prune-fetch-response: json-prune-fetch-response for JSON Lines bodies (each non-empty line pruned
// separately, re-joined with "\n"). Spec 03b 7.
function (R, ...args) {
  R.apply(R.deps["json-prune-fetch-response"], null, R.apply(R.n.aConcat, [R, { jsonl: true }], [args]));
}
