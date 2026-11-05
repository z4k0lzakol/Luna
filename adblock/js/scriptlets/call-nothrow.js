// @world: main
// call-nothrow: call-nothrow(chain). The function must exist at install time; calls that throw return
// undefined instead. Constructor calls are forwarded unchanged. Spec 03a 3.4.
function (R, ...args) {
  var A = R.safeArgs(args, 1, ["log", "debug"], 1);
  var chain = A.p[0];
  if (chain === "") return;
  var parts = R.split(chain, ".");
  var owner = R.win;
  for (var i = 0; i < parts.length - 1; i++) {
    if (parts[i] === "") return;
    try { owner = owner[parts[i]]; } catch (e) { return; }
    if (!R.isObj(owner)) return;
  }
  var prop = parts[parts.length - 1];
  if (prop === "") return;
  R.wrapMethod(owner, prop, function (t, th, a) {
    try { return R.apply(t, th, a); } catch (e) { return undefined; }
  });
}
