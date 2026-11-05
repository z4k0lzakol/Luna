// @deps: lib-json, lib-net
// @world: main
// json-edit-fetch-response: (query); vararg propsToMatch (default: all requests). The JSONPath query (json-edit) is
// applied to the parsed JSON body of matching fetch responses (lib-net response plumbing, like
// json-prune-fetch-response). Spec 03b 9.
// Internal form, first argument {trusted, xhr, jsonl, request}: trusted -> assignments allowed; xhr -> XHR
// responses; jsonl -> JSON Lines bodies; request -> the JSON request body (fetch init.body / Request body, XHR send).
function (R, ...args) {
  var o = null;
  if (args.length && args[0] !== null && typeof args[0] === "object") { o = args[0]; args = R.slice(args, 1); }
  o = o || {};
  var A = R.safeArgs(args, 1, ["propsToMatch", "log", "debug"], 1);
  var J = R.deps["lib-json"](R), N = R.deps["lib-net"](R);
  var Q = J.path(A.p[0], o.trusted === true);
  if (!Q) return;
  var M = N.matcher(A.x.propsToMatch !== undefined ? A.x.propsToMatch : "", true);
  var ed = {
    kind: o.jsonl ? "jsonl" : "json",
    test: function (req) { return M(req); },
    run: function (obj) { return Q.run(obj); }
  };
  var where = o.xhr ? "xhr" : "fetch";
  if (o.request) N.editRequest(ed, where);
  else N.editResponse(ed, where);
}
