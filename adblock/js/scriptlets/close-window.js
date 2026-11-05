// @world: main
// close-window (window-close-if): close-window([needle]). Top-level frame only. Regex needle -> tested on
// location.href; plain needle -> substring of pathname + search; empty -> always. Calls window.close()
// at document start (Luna's view decides whether the tab really closes). Spec 03a 6.2.
function (R, ...args) {
  if (!R.isTop()) return;
  var A = R.safeArgs(args, 1, ["log", "debug"], 1);
  var P = R.pattern(A.p[0], false);
  var loc = R.win.location, subject;
  try {
    subject = P.kind === "regex" ? R.str(loc.href) : R.str(loc.pathname) + R.str(loc.search);
  } catch (e) { return; }
  if (!P.test(subject)) return;
  var close = R.win.close;
  if (typeof close !== "function") return;
  try { R.apply(close, R.win, []); } catch (e) { /* ignore */ }
}
