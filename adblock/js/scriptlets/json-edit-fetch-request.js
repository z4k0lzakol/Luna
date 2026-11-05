// @deps: json-edit-fetch-response
// @world: main
// json-edit-fetch-request: (query); vararg propsToMatch. json-edit on the JSON request body of matching fetch calls. Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { request: true }], [args]));
}
