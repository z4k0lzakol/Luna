// @world: main
// prevent-navigation: (urlNeedle). Cancels Navigation API "navigate" events whose destination URL matches
// urlNeedle (pattern); "location.href" = the current URL (blocks reloads). Non-cancelable navigations pass.
// Spec 03a 6.5.
function (R, ...args) {
  var needle = R.str(args[0]);
  if (needle === "") return;
  var n = R.n, win = R.win, nav;
  try { nav = win.navigation; } catch (e) { return; }
  if (!R.isObj(nav)) return;
  var NE = win.NavigateEvent, ND = win.NavigationDestination;
  var dD = NE && R.findDesc(NE.prototype, "destination");
  var uD = ND && R.findDesc(ND.prototype, "url");
  var cD = R.findDesc(win.Event.prototype, "cancelable");
  var hD = R.findDesc(n.location, "href");
  if (!dD || !dD.desc.get || !uD || !uD.desc.get || !cD || !cD.desc.get || !hD || !hD.desc.get) return;
  var destGet = dD.desc.get, urlGet = uD.desc.get, canGet = cD.desc.get, hrefGet = hD.desc.get;
  var cur = needle === "location.href";
  var P = cur ? null : R.pattern(needle, false);
  var onNav = R.anon(function (ev) {
    var url, can;
    try {
      url = R.apply(urlGet, R.apply(destGet, ev, []), []);
      can = R.apply(canGet, ev, []);
    } catch (e) { return; }
    if (!can || typeof url !== "string") return;
    var hit;
    if (cur) {
      try { hit = url === R.apply(hrefGet, n.location, []); } catch (e) { hit = false; }
    } else {
      hit = P.test(url);
    }
    if (hit) R.apply(n.preventDefault, ev, []);
  });
  try { R.apply(n.addEventListener, nav, ["navigate", onNav]); } catch (e) { /* ignore */ }
}
