// @deps: lib-json, lib-net
// @world: main
// json-edit: (query); vararg matches. uBO-flavoured JSONPath (legacy dialect, or RFC 9535-like after "v2:")
// applied in place to the results of JSON.parse and Response.prototype.json. Untrusted: the selected nodes are
// removed (delete / splice). matches (pattern) is tested on the raw JSON text (on the serialised object for
// Response.json). Invalid query -> inert. Spec 03b 9, 02 15.
// Internal form (trusted-json-edit): first argument {trusted: true} -> assignments =JSON, +={...}, =repl({...}).
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") { trusted = args[0].trusted === true; args = R.slice(args, 1); }
  var A = R.safeArgs(args, 1, ["matches", "log", "debug"], 1);
  var J = R.deps["lib-json"](R), N = R.deps["lib-net"](R);
  var Q = J.path(A.p[0], trusted);
  if (!Q) return;
  var MP = A.x.matches !== undefined && A.x.matches !== "" ? R.pattern(A.x.matches, false) : null;
  N.onJson(function (obj, stack, text) {
    if (MP) {
      var t = text;
      if (t === null) { try { t = J.stringify(obj); } catch (e) { return; } }
      if (!MP.test(t)) return;
    }
    Q.run(obj);
  });
}
