// @deps: set-cookie
// @world: main
// trusted-set-cookie (trusted only): (name, value, [expiresOffset], [path]); varargs reload, domain,
// dontOverwrite. Any value; $now$ $currentDate$ $currentISODate$; expires seconds | 1day | 1year. Spec 03c 11.2.
function (R, ...args) {
  R.apply(R.deps["set-cookie"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
