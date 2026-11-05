// @deps: lib-json
// @world: main
// edit-object-on-setter: (chain, query). The property at chain (window-relative, deferred like set-constant) is
// trapped; an object assigned to it is edited in place with the JSONPath query (json-edit) before it is stored.
// Spec 03b 9 (signature inferred from the names + census, e.g. "edit-object-on-setter, initials, .*[?.advertiser]").
// Internal form, first argument {trusted, getter}: getter -> edit-object-on-getter (the value is edited when read).
function (R, ...args) {
  var o = null;
  if (args.length && args[0] !== null && typeof args[0] === "object") { o = args[0]; args = R.slice(args, 1); }
  o = o || {};
  var A = R.safeArgs(args, 2, ["log", "debug"], 2);
  var chain = R.trim(A.p[0]);
  if (chain === "") return;
  var J = R.deps["lib-json"](R);
  var Q = J.path(A.p[1], o.trusted === true);
  if (!Q) return;
  var run = function (v) { if (R.isObj(v)) { try { Q.run(v); } catch (e) { /* ignore */ } } return v; };
  if (o.getter) {
    R.trap(R.win, chain, { get: function (st, rcv) { return run(R.passGet(st, rcv)); } });
  } else {
    R.trap(R.win, chain, {
      init: function (st) { if (!st.desc || (!st.desc.get && !st.desc.set)) run(st.value); },
      set: function (st, v, rcv) { R.passSet(st, run(v), rcv); }
    });
  }
}
