// @world: main
// prevent-innerHTML: prevent-innerHTML([selector], [pattern]); pattern negatable. Replaces the setter of
// Element.prototype.innerHTML (getter untouched): matching assignments are ignored. Spec 03c 6.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 2);
  var n = R.n, win = R.win;
  var sel = R.trim(A.p[0]);
  var P = R.pattern(A.p[1], true);
  if (sel !== "") { try { R.apply(n.querySelectorAll, R.doc, [sel]); } catch (e) { return; } }
  var THtml = null, thToString = null;
  try { THtml = win.TrustedHTML || null; thToString = THtml ? THtml.prototype.toString : null; } catch (e) { THtml = null; }
  var isTH = function (v) {
    if (!THtml || !R.isObj(v)) return false;
    try { R.apply(thToString, v, []); return true; } catch (e) { return false; }
  };
  R.wrapAccessor(win.Element.prototype, "innerHTML", {
    set: function (t, th, a) {
      var v = a[0], text;
      if (typeof v === "string") text = v;
      else if (isTH(v)) text = R.apply(thToString, v, []);
      else text = R.str(v);
      var selOK = true;
      if (sel !== "") { try { selOK = R.nodeType(th) === 1 && R.apply(n.matches, th, [sel]); } catch (e) { selOK = false; } }
      if (selOK && P.test(text)) return undefined;
      return R.apply(t, th, a);
    }
  });
}
