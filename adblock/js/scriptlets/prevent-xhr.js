// @deps: lib-net
// @world: main
// prevent-xhr (no-xhr-if): ([propsToMatch], [bodyDirective]); vararg log. propsToMatch tests method/url only.
// A matching XMLHttpRequest is re-opened (native open) on the Luna scheme (R.SR + "x/..." or "r/<war resource>",
// CSP-ignored) so the browser performs a genuine load: status 200 "OK", trusted events in native order, every
// responseType works; responseURL is masked to the original URL and access-control-* headers are hidden.
// Without a scheme (R.SR === "") a data: URL is used. Empty propsToMatch = log-only form -> inert. Spec 03b 4.
// Internal form (trusted-prevent-xhr): first argument {trusted: true} (literal response text).
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    trusted = args[0].trusted === true;
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 2, ["log", "debug"], 1);
  var N = R.deps["lib-net"](R);
  var M = N.matcher(A.p[0], false);
  if (!M) return;
  var body = N.directive(A.p[1], trusted);
  N.fake(function (req) {
    return M(req) ? { body: body } : null;
  }, "xhr");
}
