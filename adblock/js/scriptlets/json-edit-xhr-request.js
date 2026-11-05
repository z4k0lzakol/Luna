// @deps: json-edit-fetch-response
// @world: main
// json-edit-xhr-request: (query); vararg propsToMatch. json-edit on the JSON string passed to XMLHttpRequest send(). Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true, request: true }], [args]));
}
