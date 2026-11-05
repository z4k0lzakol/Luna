// @deps: nofab
// @world: main
// nobab2 (prevent-bab2): BlockAdBlock 4.2b. Exact uBO mechanism undocumented; spec 04 5.19 minimum: define the
// BlockAdBlock constructors and instances in the never-detected state exactly like nofab.
function (R, ...args) {
  R.deps["nofab"](R);
}
