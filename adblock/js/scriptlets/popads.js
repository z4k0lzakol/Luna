// @deps: abort-on-property-write
// @world: main
// popads (popads.net, prevent-popads-net): abort-on-property-write for PopAds and popns. Spec 03c 14, 04 5.20.
function (R, ...args) {
  R.deps["abort-on-property-write"](R, "PopAds");
  R.deps["abort-on-property-write"](R, "popns");
}
