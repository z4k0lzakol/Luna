// @world: main
// abort-on-property-read (aopr): aopr(chain). Reads throw a silent ReferenceError, writes are ignored. Spec 03a 2.1.
function (R, ...args) {
  var chain = R.str(args[0]);
  if (chain === "") return;
  var msg = R.abortMsg(chain);
  R.trap(R.win, chain, {
    get: function (st) { return R.abort(msg, st.fnGet); },
    set: function () {}
  });
}
