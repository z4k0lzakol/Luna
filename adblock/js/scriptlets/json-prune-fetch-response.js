// @deps: lib-json, lib-net
// @world: main
// json-prune-fetch-response: (prunePaths, [needlePaths]); varargs propsToMatch, stackToMatch, log.
// For matching fetch() calls (propsToMatch default: all; stackToMatch negatable, tested at call time) the JSON body
// of an OK, non-opaque response is pruned; when something changed a new Response (same status/statusText/headers,
// url/type/redirected masked to the original) is returned, otherwise the original object. Spec 03b 7.
// Internal form: first argument {xhr: true} (json-prune-xhr-response), {jsonl: true} (jsonl-prune-*: every
// non-empty line of a JSON Lines body is pruned separately).
function (R, ...args) {
  var o = null;
  if (args.length && args[0] !== null && typeof args[0] === "object") { o = args[0]; args = R.slice(args, 1); }
  var xhr = !!(o && o.xhr), jsonl = !!(o && o.jsonl);
  var A = R.safeArgs(args, 2, ["propsToMatch", "stackToMatch", "log", "debug"], 1);
  var J = R.deps["lib-json"](R), N = R.deps["lib-net"](R);
  var prune = J.pruner(A.p[0], A.p[1]);
  if (!prune) return;
  var M = N.matcher(A.x.propsToMatch !== undefined ? A.x.propsToMatch : "", true);
  var SP = A.x.stackToMatch !== undefined && A.x.stackToMatch !== "" ? R.pattern(A.x.stackToMatch, true) : null;
  N.editResponse({
    kind: jsonl ? "jsonl" : "json",
    test: function (req, stack) { return M(req) && (!SP || SP.test(stack())); },
    run: function (obj) { return prune(obj); }
  }, xhr ? "xhr" : "fetch");
}
