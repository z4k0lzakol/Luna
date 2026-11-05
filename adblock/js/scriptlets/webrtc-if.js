// @world: main
// webrtc-if: (needle). RTCPeerConnection keeps only ICE servers where needle (pattern) matches one of urls /
// username / credential; applies to the constructor and setConfiguration. The page's config object is not
// mutated (a copy is passed on). Spec 03a 7.2.
function (R, ...args) {
  var needle = R.str(args[0]);
  if (needle === "") return;
  var n = R.n, win = R.win;
  var RPC = win.RTCPeerConnection;
  if (typeof RPC !== "function") return;
  var P = R.pattern(needle, false);
  function strHit(v) { return typeof v === "string" && v !== "" && P.test(v); }
  function keep(s) {
    if (!R.isObj(s)) return false;
    try {
      var u = s.urls;
      if (u === undefined) u = s.url;
      var list = n.isArray(u) ? u : [u];
      for (var i = 0; i < list.length; i++) if (strHit(list[i])) return true;
      return strHit(s.username) || strHit(s.credential);
    } catch (e) { return false; }
  }
  function filter(cfg) {
    if (!R.isObj(cfg)) return cfg;
    var servers;
    try { servers = cfg.iceServers; } catch (e) { return cfg; }
    if (!n.isArray(servers)) return cfg;
    var kept = [];
    for (var i = 0; i < servers.length; i++) if (keep(servers[i])) kept[kept.length] = servers[i];
    var copy = n.assign(n.create(win.Object.prototype), cfg);
    copy.iceServers = kept;
    return copy;
  }
  var wk = win.webkitRTCPeerConnection === RPC;
  var px = R.wrapCtor(win, "RTCPeerConnection", function (t, a, nt) {
    var b = R.slice(a, 0);
    if (b.length) b[0] = filter(b[0]);
    return n.construct(t, b, nt === px ? t : nt);
  });
  if (!px) return;
  if (wk) R.redefine(win, "webkitRTCPeerConnection", px);
  R.redefine(RPC.prototype, "constructor", px);
  R.wrapMethod(RPC.prototype, "setConfiguration", function (t, th, a) {
    var b = R.slice(a, 0);
    if (b.length) b[0] = filter(b[0]);
    return R.apply(t, th, b);
  });
}
