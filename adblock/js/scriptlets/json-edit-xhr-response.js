// @deps: json-edit-fetch-response
// @world: main
// json-edit-xhr-response: (query); vararg propsToMatch (method/url). json-edit on matching XHR responses (""/text/json types). Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true }], [args]));
}
