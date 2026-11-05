// @world: main
// alert-buster: window.alert() returns undefined without showing a dialog (silent, no console). Spec 03a 6.6.
function (R, ...args) {
  R.wrapMethod(R.win, "alert", function () { return undefined; });
}
