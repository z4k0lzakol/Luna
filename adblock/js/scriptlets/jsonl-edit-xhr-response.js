// @deps: json-edit-fetch-response
// @world: main
// jsonl-edit-xhr-response: (query); vararg propsToMatch. json-edit on every line of JSON Lines XHR responses. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true, jsonl: true }], [args]));
}
