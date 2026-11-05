// @world: main
// proxy-apply-config: ({"skipToString": true}) - uBO tuning knob for its own Proxy helper. Spec 03a 8.6.
// Luna's Function.prototype.toString mask is installed lazily once per realm and is cheap (one WeakMap lookup),
// and turning it off would make every wrapped native print without its name (a detection vector), so the knob
// is accepted, validated and ignored (inert).
function (R, ...args) {
  try { R.apply(R.n.JSON_parse, R.win.JSON, [R.str(args[0])]); } catch (e) { /* invalid config: inert */ }
}
