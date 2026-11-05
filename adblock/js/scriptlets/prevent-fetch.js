// @deps: lib-net
// @world: main
// prevent-fetch (no-fetch-if): ([propsToMatch], [bodyDirective], [responseConfig]); varargs throttle, log.
// Matching fetch() calls never reach the network: a Response is built in the page (status 200 "OK", content-type,
// content-length; type basic/cors/opaque like a real one; url/type/redirected/... masked on Response.prototype)
// and resolved after a macrotask (+ throttle ms). Empty propsToMatch = uBO log-only form -> inert. Spec 03b 2.
// Internal form (trusted-prevent-fetch): first argument {trusted: true} (literal bodies, config headers).
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    trusted = args[0].trusted === true;
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 3, ["throttle", "log", "debug"], 1);
  var N = R.deps["lib-net"](R);
  var M = N.matcher(A.p[0], false);
  if (!M) return;
  var cfg = N.config(A.p[2], trusted);
  if (!cfg) return;
  var body = N.directive(A.p[1], trusted);
  var th = 0;
  if (A.x.throttle !== undefined && R.apply(R.n.reTest, /^\d+$/, [A.x.throttle])) th = R.n.Number(A.x.throttle);
  N.fake(function (req) {
    return M(req) ? { body: body, cfg: cfg, throttle: th } : null;
  }, "fetch");
}
