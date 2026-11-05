// @deps: set-constant
// @world: main
// prebid-ads: the content of the prebid-ads.js bait file - canRunAds = true, isAdBlockActive = false - pinned with
// set-constant semantics so that a later page write of the same type cannot flip them. Spec 03c 14, 04 5.21.
function (R, ...args) {
  R.deps["set-constant"](R, "canRunAds", "true");
  R.deps["set-constant"](R, "isAdBlockActive", "false");
}
