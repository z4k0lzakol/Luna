// @world: main
// nowebrtc: no arguments. `new RTCPeerConnection(...)` (and the webkit alias) returns an inert peer connection: a
// real EventTarget whose prototype is the genuine RTCPeerConnection.prototype (instanceof, toStringTag and
// descriptors unchanged). The prototype's methods/accessors are masked wrappers that, for these inert objects only,
// do nothing: createOffer / createAnswer / setLocalDescription / setRemoteDescription / addIceCandidate / getStats
// return never-settling promises, createDataChannel an inert RTCDataChannel (readyState "connecting"),
// getSenders/getReceivers/getTransceivers [], descriptions null, states "new"/"stable", on* handlers stored.
// Calling the constructor without new throws the native TypeError. No network activity. Spec 03a 7.1.
function (R) {
  var n = R.n, win = R.win, apply = R.apply;
  var RPC = win.RTCPeerConnection;
  if (typeof RPC !== "function") return;
  var ET = win.EventTarget, PCP = RPC.prototype, DC = win.RTCDataChannel, DCP = DC && DC.prototype;
  var WMp = n.WeakMap.prototype, wmGet = WMp.get, wmSet = WMp.set;
  var state = new n.WeakMap();   // inert object -> {dc: bool, st, label, h: {on*: handler}, v: {prop: value}}
  function info(o) { return R.isObj(o) ? apply(wmGet, state, [o]) : undefined; }
  var never = function () { return new n.Promise(function () {}); };
  var PCV = { signalingState: "stable", iceGatheringState: "new", iceConnectionState: "new", connectionState: "new" };
  var DCV = { bufferedAmount: 0, bufferedAmountLowThreshold: 0, ordered: true, protocol: "", negotiated: false,
              maxRetransmits: null, maxPacketLifeTime: null, id: null, binaryType: "arraybuffer", reliable: true,
              priority: "low" };
  function make(proto, dc, label) {
    var o = new ET();
    n.setPrototypeOf(o, proto);
    apply(wmSet, state, [o, { dc: dc, st: dc ? "connecting" : "", label: label, h: n.create(null), v: n.create(null) }]);
    return o;
  }
  function pcMethod(k, th, a) {
    switch (k) {
      case "createOffer": case "createAnswer": case "setLocalDescription": case "setRemoteDescription":
      case "addIceCandidate": case "getStats": case "generateCertificate":
        return never();
      case "createDataChannel":
        return DCP ? make(DCP, true, R.str(a[0])) : null;
      case "getSenders": case "getReceivers": case "getTransceivers":
        return [];
      case "getConfiguration":
        return { iceServers: [], iceTransportPolicy: "all", bundlePolicy: "balanced", rtcpMuxPolicy: "require",
                 iceCandidatePoolSize: 0, certificates: [] };
    }
    return undefined;
  }
  function dcMethod(k, th) {
    if (k === "close") { var s = info(th); if (s) s.st = "closed"; }
    return undefined;
  }
  function getVal(k, th) {
    var s = info(th);
    if (R.startsWith(k, "on")) return s.h[k] !== undefined ? s.h[k] : null;
    if (k in s.v) return s.v[k];
    if (s.dc) {
      if (k === "readyState") return s.st;
      if (k === "label") return s.label;
      return k in DCV ? DCV[k] : null;
    }
    return k in PCV ? PCV[k] : null;
  }
  function setVal(k, th, v) {
    var s = info(th);
    if (R.startsWith(k, "on")) s.h[k] = typeof v === "function" || (v !== null && typeof v === "object") ? v : null;
    else s.v[k] = v;
  }
  function patch(proto, dc) {
    var keys = n.ownKeys(proto);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (typeof k !== "string" || k === "constructor") continue;
      var d = n.getOwnPropertyDescriptor(proto, k);
      if (!d) continue;
      (function (k, d) {
        if (typeof d.value === "function") {
          R.wrapMethod(proto, k, function (t, th, a) {
            var s = info(th);
            if (s && s.dc === dc) return dc ? dcMethod(k, th) : pcMethod(k, th, a);
            return apply(t, th, a);
          });
        } else if (d.get) {
          R.wrapAccessor(proto, k, {
            get: function (t, th, a) { var s = info(th); return s && s.dc === dc ? getVal(k, th) : apply(t, th, a); },
            set: function (t, th, a) { var s = info(th); if (s && s.dc === dc) setVal(k, th, a[0]); else apply(t, th, a); }
          });
        }
      })(k, d);
    }
  }
  patch(PCP, false);
  if (DCP) patch(DCP, true);
  var px = R.wrapCtor(win, "RTCPeerConnection", function (t, a, nt) {
    var proto = PCP;
    try { var p = n.get(nt, "prototype"); if (R.isObj(p)) proto = p; } catch (e) { proto = PCP; }
    return make(proto, false, "");
  });
  if (!px) return;
  R.redefine(PCP, "constructor", px);
  if (win.webkitRTCPeerConnection === RPC) R.redefine(win, "webkitRTCPeerConnection", px);
}
