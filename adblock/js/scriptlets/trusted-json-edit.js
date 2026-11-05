// @deps: json-edit
// @world: main
// trusted-json-edit: json-edit with assignments (=JSON, +={...} merge, =repl({"pattern"|"regex", "replacement"}),
// "${now}" placeholder). Spec 03b 9.
function (R, ...args) {
  R.apply(R.deps["json-edit"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
