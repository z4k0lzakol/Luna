// @world: main
// set-constant (set): set(chain, value, [legacyRunAt]) ; varargs runAt, as, stack. Spec 03a 3.5.
// Internal form used by trusted-set-constant: first argument {trusted: true} (object, never from lists).
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    trusted = args[0].trusted === true;
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 3, ["runAt", "as", "stack", "log", "debug"], 2);
  var chain = A.p[0];
  if (chain === "") return;
  var c = R.constant(A.p[1], trusted, chain);
  if (!c) return;
  var when = A.x.runAt !== undefined ? A.x.runAt : A.p[2];
  var as = A.x.as !== undefined ? A.x.as : "";
  if (as === "asFunction") as = "function";
  else if (as === "asCallback") as = "callback";
  else if (as === "asResolved") as = "resolved";
  else if (as === "asRejected") as = "rejected";
  var base = c.v, n = R.n, win = R.win;
  var lazy = null, value = base;
  if (as === "function") {
    value = R.fn(R.anon(function () { return base; }), "function () {}");
  } else if (as === "callback") {
    value = R.fn(R.anon(function () { return R.fn(R.anon(function () { return base; }), "function () {}"); }),
      "function () { return function () {}; }");
  } else if (as === "resolved" || as === "rejected") {
    lazy = function () {
      return as === "resolved" ? R.apply(n.promiseResolve, n.Promise, [base]) : R.apply(n.promiseReject, n.Promise, [base]);
    };
  } else if (as !== "") {
    return;
  }
  var made = false, promised;
  function current() {
    if (!lazy) return value;
    if (!made) { made = true; promised = lazy(); }
    return promised;
  }
  var cmpType = lazy ? "object" : typeof value;
  var stackP = A.x.stack !== undefined && A.x.stack !== "" ? R.pattern(A.x.stack, true) : null;
  function isNil(v) { return v === undefined || v === null; }
  var install = function () {
    R.trap(win, chain, {
      defer: "strict",
      init: function (st) {
        var v0;
        try { v0 = R.passGet(st, st.owner); } catch (e) { v0 = undefined; }
        if (!trusted && !isNil(v0) && !lazy && !isNil(value) && typeof v0 !== cmpType) return false;
        st.cur = null;
        st.repl = false;
        return true;
      },
      get: function (st, rcv) {
        if (st.repl) return st.cur;
        if (stackP && !stackP.test(R.stack(st.fnGet))) return R.passGet(st, rcv);
        return current();
      },
      set: function (st, v, rcv) {
        if (st.repl) { st.cur = v; return; }
        if (stackP && !stackP.test(R.stack(st.fnSet))) { R.passSet(st, v, rcv); return; }
        if (!lazy && !isNil(value) && !isNil(v) && typeof v !== cmpType) { st.repl = true; st.cur = v; }
      },
      fixed: function (o, p, d) {
        if (d.writable && !("get" in d)) { try { o[p] = current(); return true; } catch (e) { return false; } }
        return false;
      }
    });
  };
  R.onReady(install, when);
}
