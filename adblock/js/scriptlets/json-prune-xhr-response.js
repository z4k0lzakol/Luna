// @deps: json-prune-fetch-response
// @world: main
// json-prune-xhr-response: (prunePaths, [needlePaths]); varargs propsToMatch (method/url), stackToMatch, log.
// The response / responseText getters of a matching XHR return the pruned value once readyState is 4 (computed
// once, cached): responseType ""/"text" -> parse, prune, re-stringify; "json" -> pruned in place. Spec 03b 7.
function (R, ...args) {
  R.apply(R.deps["json-prune-fetch-response"], null, R.apply(R.n.aConcat, [R, { xhr: true }], [args]));
}
