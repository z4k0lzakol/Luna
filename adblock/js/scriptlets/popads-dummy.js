// @world: main
// popads-dummy (set-popads-dummy): window.PopAds and window.popns always read as one dummy object; writes are
// ignored, so the PopAds loader believes it already ran. Accessors stay configurable (a page defineProperty must
// not throw). Spec 03c 14, 04 5.20.
function (R, ...args) {
  var dummy = R.n.create(R.win.Object.prototype);
  var names = ["PopAds", "popns"];
  for (var i = 0; i < names.length; i++) {
    R.defineAccessor(R.win, names[i], function () { return dummy; }, function () {}, true);
  }
}
