// @deps: lib-json
// @world: main
// edit-element-object: (selector, query, [timeoutMs]). The JSONPath query (json-edit) is applied in place to the
// JS object of every element matching selector (each element once): elements present now and those added later,
// watched with a MutationObserver until timeoutMs (default: until the window load event). Spec 03b 9.
// Internal form (trusted-edit-element-object): first argument {trusted: true}.
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") { trusted = args[0].trusted === true; args = R.slice(args, 1); }
  var A = R.safeArgs(args, 3, ["log", "debug"], 3);
  var sel = R.trim(A.p[0]);
  if (sel === "") return;
  var J = R.deps["lib-json"](R), n = R.n, doc = R.doc;
  var Q = J.path(A.p[1], trusted);
  if (!Q) return;
  try { R.apply(n.querySelector, doc, [sel]); } catch (e) { return; }
  var tm = R.trim(A.p[2]), ms = -1;
  if (tm !== "") {
    if (!R.apply(n.reTest, /^\d+$/, [tm])) return;
    ms = n.Number(tm);
  }
  var seen = new n.WeakSet(), wsHas = n.WeakSet.prototype.has, wsAdd = n.WeakSet.prototype.add;
  var edit = function (el) {
    if (R.apply(wsHas, seen, [el])) return;
    R.apply(wsAdd, seen, [el]);
    try { Q.run(el); } catch (e) { /* ignore */ }
  };
  var scan = function () {
    var l;
    try { l = R.apply(n.querySelectorAll, doc, [sel]); } catch (e) { return; }
    for (var i = 0; i < l.length; i++) edit(l[i]);
  };
  scan();
  var stop = R.observe(doc, { childList: true, subtree: true }, scan);   // records are batched per microtask
  if (ms >= 0) R.later(function () { scan(); stop(); }, ms);
  else R.onReady(function () { scan(); stop(); }, "complete");
}
