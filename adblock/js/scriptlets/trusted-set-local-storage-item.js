// @deps: set-local-storage-item
// @world: main
// trusted-set-local-storage-item (trusted only): (key, value) with any value and $now$ / $currentDate$ /
// $currentISODate$ placeholders; $remove$ removes. Spec 03c 12.2.
function (R, ...args) {
  R.apply(R.deps["set-local-storage-item"], null, R.apply(R.n.aConcat, [R, { trusted: true }], [args]));
}
