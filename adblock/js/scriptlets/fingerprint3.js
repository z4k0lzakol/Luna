// @world: main
// fingerprint3 (fingerprintjs3): FingerprintJS v3 (open-source API) shim injected at document start.
// Spec 03c 14, 04 5.16. window.FingerprintJS = {load(), hashComponents(), componentsToDebugString()};
// agent.get() -> Promise<{visitorId, confidence: {score: 0.5}, components: {}, version: "3.4.2"}> with a random
// 32-hex visitorId per page load. Pinned set-constant style (same-type writes ignored).
function (R, ...args) {
  var n = R.n, win = R.win, M = win.Math;
  var HEX = "0123456789abcdef", id = "";
  for (var i = 0; i < 32; i++) {
    var d = R.apply(n.Math_floor, M, [R.apply(n.Math_random, M, []) * 16]);
    id += R.slice(HEX, d, d + 1);
  }
  function pub(f) { return R.fn(f, "function () {}"); }
  function resolved(v) { return R.apply(n.promiseResolve, n.Promise, [v]); }
  var agent = {
    get: pub(R.anon(function () {
      return resolved({ visitorId: id, confidence: { score: 0.5 }, components: {}, version: "3.4.2" });
    }))
  };
  var api = {
    load: pub(R.anon(function () { return resolved(agent); })),
    hashComponents: pub(R.anon(function () { return id; })),
    componentsToDebugString: pub(R.anon(function () { return "{}"; }))
  };
  var cur = api;
  R.defineAccessor(win, "FingerprintJS", function () { return cur; }, function (rcv, v) {
    if (v !== undefined && v !== null && typeof v !== "object") cur = v;
  }, true);
}
