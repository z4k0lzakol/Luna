// @deps: lib-net
// @world: main
// trusted-replace-fetch-response (trusted-rpfr): (pattern, [replacement], [propsToMatch]); vararg includes.
// pattern "*" = the whole body; /re/flags = regex with its own flags; plain text = every occurrence. replacement
// may use $1 references. includes (pattern) must be found in the body first. propsToMatch "" or "*" = all.
// Unchanged bodies keep the original Response object. Empty pattern = log-only form -> inert. Spec 03b 12.
// Internal form: first argument {xhr: true} (trusted-replace-xhr-response: text and json response types).
function (R, ...args) {
  var xhr = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") { xhr = args[0].xhr === true; args = R.slice(args, 1); }
  var A = R.safeArgs(args, 3, ["includes", "log", "debug"], 2);
  var pat = A.p[0], rep = A.p[1];
  if (pat === "") return;
  var N = R.deps["lib-net"](R);
  var M = N.matcher(A.p[2], true);
  var INC = A.x.includes !== undefined && A.x.includes !== "" ? R.pattern(A.x.includes, false) : null;
  var P = pat === "*" ? null : R.pattern(pat, false);
  var run = function (text) {
    if (INC && !INC.test(text)) return null;
    if (!P) return rep;
    if (P.kind === "regex") { P.re.lastIndex = 0; return R.sreplace(text, P.re, rep); }
    var parts = R.split(text, P.text);
    if (parts.length < 2) return null;
    var out = parts[0], rr = R.sreplace(P.text, /^[\s\S]*$/, rep);   // "$&"-style references like replace()
    for (var i = 1; i < parts.length; i++) out += rr + parts[i];
    return out;
  };
  N.editResponse({
    kind: "text",
    test: function (req) { return M(req); },
    run: run
  }, xhr ? "xhr" : "fetch");
}
