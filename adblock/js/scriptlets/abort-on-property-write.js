// @world: main
// abort-on-property-write (aopw): aopw(chain). Writes throw a silent ReferenceError, reads return the
// value captured at install time. Spec 03a 2.2.
function (R, ...args) {
  var chain = R.str(args[0]);
  if (chain === "") return;
  var msg = R.abortMsg(chain);
  R.trap(R.win, chain, {
    init: function (st) {
      if (st.desc && st.desc.get) {
        try { st.value = R.passGet(st, st.owner); } catch (e) { st.value = undefined; }
      }
    },
    get: function (st) { return st.value; },
    set: function (st) { R.abort(msg, st.fnSet); }
  });
}
