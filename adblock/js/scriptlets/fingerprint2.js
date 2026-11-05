// @world: main
// fingerprint2 (fingerprintjs2): FingerprintJS v2 shim injected at document start. Spec 03c 14, 04 5.15.
// window.Fingerprint2 = constructor (prototype.get(cb) -> async cb(hash, components)) with statics get, getPromise,
// getV18, x64hash128, VERSION 2.1.4 and the NOT_AVAILABLE/ERROR/EXCLUDED constants. hash = 32 random hex chars per
// page load. The global is pinned set-constant style: a later write of the same type (the real library) is
// ignored, a write of another type wins. Exposed functions print as plain "function () {}".
function (R, ...args) {
  var n = R.n, win = R.win, M = win.Math;
  var imul = M.imul, floor = n.Math_floor, random = n.Math_random;
  var numToStr = win.Number.prototype.toString;
  var HEX = "0123456789abcdef";
  function hex(k) {
    var s = "";
    for (var i = 0; i < k; i++) {
      var d = R.apply(floor, M, [R.apply(random, M, []) * 16]);
      s += R.slice(HEX, d, d + 1);
    }
    return s;
  }
  var hash = hex(32);
  var nav = win.navigator, ua = "", lang = "", tz = 0;
  try { ua = R.str(nav.userAgent); lang = R.str(nav.language); } catch (e) { /* ignore */ }
  try { tz = R.apply(win.Date.prototype.getTimezoneOffset, new win.Date(), []); } catch (e) { tz = 0; }
  function components() {
    return [{ key: "userAgent", value: ua }, { key: "language", value: lang }, { key: "timezoneOffset", value: tz }];
  }
  function pub(f) { return R.fn(f, "function () {}"); }
  function later(fn, a, b) {
    if (typeof fn !== "function") return;
    R.later(function () { R.apply(fn, undefined, [a, b]); }, 1);
  }
  function cbOf(a, b) { return typeof a === "function" ? a : b; }
  var Fingerprint2 = pub(R.anon(function (options) {
    if (R.isObj(this)) this.options = R.isObj(options) ? options : {};
  }));
  Fingerprint2.prototype.get = pub(R.anon(function (cb) { later(cb, hash, components()); }));
  Fingerprint2.get = pub(R.anon(function (a, b) { later(cbOf(a, b), components()); }));
  Fingerprint2.getPromise = pub(R.anon(function () {
    return R.apply(n.promiseResolve, n.Promise, [components()]);
  }));
  Fingerprint2.getV18 = pub(R.anon(function (a, b) { later(cbOf(a, b), hash, components()); }));
  Fingerprint2.x64hash128 = pub(R.anon(function (key, seed) {
    var s = R.str(key), sd = (typeof seed === "number" ? seed : 0) | 0;
    var h = [sd ^ 0x6a09e667, 0xbb67ae85 ^ sd, 0x3c6ef372, 0xa54ff53a];
    for (var i = 0; i < s.length; i++) {
      var c = R.apply(n.sCharCodeAt, s, [i]);
      for (var j = 0; j < 4; j++) {
        h[j] = R.apply(imul, M, [h[j] ^ (c + j * 131), 0x9e3779b1 + j * 2]) >>> 0;
        h[j] = (h[j] << 13 | h[j] >>> 19) >>> 0;
      }
    }
    var out = "";
    for (var k = 0; k < 4; k++) {
      var x = R.apply(imul, M, [h[k] ^ h[(k + 1) % 4] >>> 15, 0x85ebca6b]) >>> 0;
      out += R.slice("00000000" + R.apply(numToStr, x, [16]), -8);
    }
    return out;
  }));
  Fingerprint2.VERSION = "2.1.4";
  Fingerprint2.NOT_AVAILABLE = "not available";
  Fingerprint2.ERROR = "error";
  Fingerprint2.EXCLUDED = "excluded";
  var cur = Fingerprint2;
  R.defineAccessor(win, "Fingerprint2", function () { return cur; }, function (rcv, v) {
    if (v !== undefined && v !== null && typeof v !== "function") cur = v;
  }, true);
}
