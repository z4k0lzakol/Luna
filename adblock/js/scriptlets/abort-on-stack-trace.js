// @world: main
// abort-on-stack-trace (aost): aost(chain, needle). Aborts reads/writes of chain when the normalised stack
// ("stackDepth:N\tfn@url:L:1\t...", inlineScript/injectedScript) matches needle ("!" negates). Spec 03a 2.4.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 1);
  var chain = A.p[0];
  if (chain === "" || A.p[1] === "") return;
  var P = R.pattern(A.p[1], true), msg = R.abortMsg(chain);
  var busy = false;
  function check(fn) {
    if (busy) return;
    busy = true;
    var hit = false;
    try { hit = P.test(R.stack(fn)); } catch (e) { hit = false; } finally { busy = false; }
    if (hit) R.abort(msg, fn);
  }
  R.trap(R.win, chain, {
    get: function (st, rcv) { check(st.fnGet); return R.passGet(st, rcv); },
    set: function (st, v, rcv) { check(st.fnSet); R.passSet(st, v, rcv); }
  });
}
