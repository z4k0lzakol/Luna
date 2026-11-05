"""SCRIPTLETS-3 scriptlets in a real QtWebEngine (MainWorld, DocumentCreation, subframes), built through
scriptlets.build(). Run: python -I tests/adblock/test_scriptlets3_qt.py   (~25 s, needs PyQt6-WebEngine)

Groups (each served on three hosts):  <g>a.localhost  scriptlets, plain page
                                      <g>b.localhost  same scriptlets, strict CSP + enforced Trusted Types + report-uri
                                      <g>z.localhost  no scriptlets (baseline for behaviour, toString, globals)
  g1  alert-buster, window.name-defuser, trusted-set-constant, set-constant edge values, trusted-suppress-native-
      method, trusted-override-element-method, trusted-replace-outbound-text, prevent-navigation (pattern),
      overlay-buster, prevent-dialog, webrtc-if, prevent-clipboard-write, proxy-apply-config,
      freeze-element-property, multiup, spoof-css, nofab, nobab, popads, prebid-ads, fingerprint2/3, google-ima,
      ampproject_v0, inert names (aell, addEventListener-logger, golem.de, no-floc, csp, sharedWorker-defuser)
  g2  nobab2, popads-dummy, noeval-silent, trusted-* dropped from an untrusted source
  g3  prevent-navigation location.href (reload) + pattern on a cross-document navigation
  g4  remove-cache-storage-item
Stealth: wrapped natives keep toString/name/length/own keys/descriptor attributes (vs baseline, also from a fresh
about:blank iframe), exposed surrogate functions do not print scriptlet source, no leaked globals beyond the
emulated APIs, no console output, no error events, no CSP/TT violation events or reports.
"""
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
_TMP = tempfile.mkdtemp(prefix="luna-s3-test-")
os.environ["USERPROFILE"] = _TMP
os.environ["HOME"] = _TMP

from adblock import scriptlet_names as names  # noqa: E402
from adblock import scriptlets  # noqa: E402


def _watchdog(sec):
    def boom():
        print("WATCHDOG: %ss exceeded" % sec, flush=True)
        os._exit(3)
    t = threading.Timer(sec, boom)
    t.daemon = True
    t.start()


_watchdog(180)

FAILS, COUNT = [], [0]


def check(cond, label, extra=None):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
        print("FAIL:", label, "" if extra is None else repr(extra)[:500], flush=True)


MINE = ["alert-buster", "window.name-defuser", "trusted-set-constant", "trusted-suppress-native-method",
        "trusted-override-element-method", "trusted-replace-outbound-text", "prevent-navigation", "overlay-buster",
        "prevent-dialog", "webrtc-if", "prevent-clipboard-write", "proxy-apply-config", "remove-cache-storage-item",
        "freeze-element-property", "multiup", "nofab", "nobab", "nobab2", "popads", "popads-dummy",
        "prebid-ads", "fingerprint2", "fingerprint3", "google-ima", "ampproject_v0", "aell",
        "addEventListener-logger", "golem.de", "no-floc", "csp", "sharedWorker-defuser"]

# ------------------------------------------------------------------ pages
HEAD = r"""<!doctype html><html><head><meta charset=utf-8><title>t</title>
<script>
var T = {errs: 0, viol: 0, vlog: [], rej: 0};
window.onerror = function () { T.errs++; };
addEventListener('error', function () { T.errs++; });
addEventListener('unhandledrejection', function () { T.rej++; });
document.addEventListener('securitypolicyviolation', function (e) { T.viol++; T.vlog.push(e.violatedDirective + '|' + e.sample); });
var CSPPAGE = location.hostname.charAt(2) === 'b';
var BASE = location.hostname.charAt(2) === 'z';
</script>
"""

G1_HEAD = r"""<style amp-boilerplate>body{animation:-amp-start 8s steps(1,end) 0s 1 normal both}@keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}</style>
</head><body>
<dialog class=cookie open id=dlg1>cookie</dialog><dialog id=dlg2>other</dialog>
<div class=bait id=bait style="display:none;width:10px">x</div><div id=nobait style="display:none">y</div>
<div id=frz class=a></div><div id=frz2 class=a></div>
<a id=blank href="#never" target=_blank>b</a><a id=self href="#tome-ok">s</a>
<input id=tome-throw><div id=tome-c data-x=1></div>
<form id=muf action="/never"><button id=mub type=submit>mirror</button></form>
<iframe id=child name=fr1 src="/child.html"></iframe>
<script src="/ext.js"></script>
"""

G1_BODY = r"""
<script>
T.wname = window.name;
T.alert = String(alert('hi'));
// trusted-set-constant
T.tsc1 = JSON.stringify(window.tsc1); T.tsc2 = window.tsc2; T.tsc3 = window.tsc3; T.tsc4 = window.tsc4;
T.tsc5 = window.tsc5; T.tsc6 = typeof window.tsc6 === 'function' ? JSON.stringify(tsc6()) : typeof window.tsc6;
T.pixelDepth = screen.pixelDepth; T.colorDepth = typeof screen.colorDepth;
// set-constant edge values
window.sce = {neg: 5}; T.sce_neg = sce.neg;
T.sce_max = window.sce_max; T.sce_over = ['sce_over' in window, typeof window.sce_over];
T.sce_q = window.sce_q;
try { T.sce_arr = [Array.isArray(sce_arr), sce_arr.length, sce_arr === sce_arr]; } catch (e) { T.sce_arr = 'ERR'; }
try { T.sce_obj = [JSON.stringify(sce_obj), sce_obj === sce_obj]; } catch (e) { T.sce_obj = 'ERR'; }
try { T.sce_cb = typeof sce_cb(); } catch (e) { T.sce_cb = 'ERR'; }
try { sce_pr().then(function (r) { T.sce_pr = r instanceof Response; }); } catch (e) { T.sce_pr = 'ERR'; }
try { sce_pj().then(function () { T.sce_pj = 'res'; }, function () { T.sce_pj = 'rej'; }); } catch (e) { T.sce_pj = 'ERR'; }
try { sce_throw(); T.sce_throw = 'no'; } catch (e) { T.sce_throw = e.name; }
T.sce_yes = window.sce_yes;
try { T.sce_true = [sce_true(), Function.prototype.toString.call(sce_true)]; } catch (e) { T.sce_true = 'ERR'; }
try { sce_res.then(function (v) { T.sce_res = v; }); } catch (e) { T.sce_res = 'ERR'; }
T.sce_rej_in = 'sce_rej' in window;
try { sce_rej.catch(function (v) { T.sce_rej = 'rej:' + v; }); } catch (e) { T.sce_rej = 'ERR'; }
try { T.sce_cbv = sce_cbv()(); } catch (e) { T.sce_cbv = 'ERR'; }
T.sce_legacy0 = typeof window.sce_legacy;
T.sce_bad = typeof window.sce_bad;
var sce_undef = 5; T.sce_undef = typeof sce_undef;
var sce_null = 7; T.sce_null = sce_null;
// trusted-suppress-native-method
try { document.querySelector('#tsnm'); T.tsnm_q = 'no'; } catch (e) { T.tsnm_q = e.name + ':' + e.message; }
T.tsnm_q2 = String(document.querySelector('#nobait'));
T.tsnm_ls_ret = String(localStorage.setItem('adb_k', '1')); localStorage.setItem('ok_k', '1');
T.tsnm_ls = [localStorage.getItem('adb_k'), localStorage.getItem('ok_k')];
try { Math.max(7, 8); T.tsnm_max = 'no'; } catch (e) { T.tsnm_max = e.message; }
T.tsnm_max2 = Math.max(7, 9);
try { JSON.stringify([2, 1, 3]); T.tsnm_arr = 'no'; } catch (e) { T.tsnm_arr = e.message; }
T.tsnm_arr2 = JSON.stringify([1, 3]);
try { JSON.stringify({k: 'v', z: 1}); T.tsnm_obj = 'no'; } catch (e) { T.tsnm_obj = 'aborted'; }
T.tsnm_obj2 = JSON.stringify({k: 'w'});
try { atob('YWRz'); T.tsnm_re = 'no'; } catch (e) { T.tsnm_re = 'aborted'; }
T.tsnm_re2 = atob('b2s=');
try { document.getElementById('x-rawneedle-y'); T.tsnm_raw = 'no'; } catch (e) { T.tsnm_raw = 'aborted'; }
var hold = document.createElement('div'); hold.append(document.createElement('img')); T.tsnm_img = hold.childNodes.length;
hold.append(document.createElement('span')); T.tsnm_img2 = hold.childNodes.length;
function tsnmStackFn() { return document.createComment('c1'); }
try { tsnmStackFn(); T.tsnm_st = 'no'; } catch (e) { T.tsnm_st = 'aborted'; }
T.tsnm_st2 = String(document.createComment('c1'));
try { (function () {}).constructor('debugger'); T.tsnm_fn = 'no'; } catch (e) { T.tsnm_fn = e.name; }
if (!CSPPAGE) { try { T.tsnm_fn2 = (function () {}).constructor('return 5')(); } catch (e) { T.tsnm_fn2 = 'ERR'; } }
// trusted-override-element-method
document.getElementById('blank').addEventListener('click', function () { T.blank_clicked = 1; });
T.toem1 = String(document.getElementById('blank').click());
document.getElementById('self').click(); T.toem2 = location.hash;
try { document.getElementById('tome-throw').focus(); T.toem3 = 'no'; } catch (e) { T.toem3 = e.message; }
T.toem4 = document.getElementById('tome-c').getAttribute('data-x');
T.toem5 = document.getElementById('bait').getAttribute('class');
var det = document.createElement('details'); det.addEventListener('click', function () { T.det_click = 1; }); det.click();
var dv = document.createElement('div'); dv.addEventListener('click', function () { T.div_click = 1; }); dv.click();
T.own_click = [HTMLDetailsElement.prototype.hasOwnProperty('click'), HTMLAnchorElement.prototype.hasOwnProperty('click'),
               HTMLSpanElement.prototype.hasOwnProperty('setAttribute'), HTMLInputElement.prototype.hasOwnProperty('getAttribute')];
var sp = document.createElement('span');
try { sp.setAttribute('data-ad', '1'); T.scope_tsnm = 'no'; } catch (e) { T.scope_tsnm = 'aborted'; }
dv.setAttribute('data-ad', '1'); T.scope_tsnm2 = dv.getAttribute('data-ad');
var inp = document.createElement('input'); inp.setAttribute('data-y', 'ad'); dv.setAttribute('data-y', 'ad');
T.scope_trot = [inp.getAttribute('data-y'), dv.getAttribute('data-y')];
// trusted-replace-outbound-text
T.trot1 = atob(btoa('x adblock=1 adblock=1'));
T.trot2 = decodeURIComponent('foo-foo');
T.trot3 = ['  aaKEEP '.trim(), ' aa '.trim()];
T.trot4 = JSON.stringify({adon: true});
T.trot5 = [btoa('evil'), btoa('nice')];
// prevent-navigation (pattern, same-document)
location.hash = 'werbeblocker'; T.pn1 = location.hash;
location.hash = 'pn-ok'; T.pn2 = location.hash;
// webrtc-if
try {
  var rcfg = {iceServers: [{urls: 'stun:goodstun.example:3478'}, {urls: ['stun:bad.example:3478']}]};
  var pc = new RTCPeerConnection(rcfg);
  T.rtc = [pc.getConfiguration().iceServers.length, rcfg.iceServers.length, pc instanceof RTCPeerConnection,
           RTCPeerConnection.name, typeof webkitRTCPeerConnection === 'undefined' || webkitRTCPeerConnection === RTCPeerConnection,
           pc.constructor === RTCPeerConnection, Object.getPrototypeOf(pc) === RTCPeerConnection.prototype];
  pc.setConfiguration({iceServers: [{urls: 'stun:bad2.example'}]}); T.rtc2 = pc.getConfiguration().iceServers.length;
  pc.close();
} catch (e) { T.rtc = 'ERR ' + e; }
// prevent-clipboard-write
T.body0 = document.body.childElementCount;
navigator.clipboard.writeText('powershell -enc AAA').then(function () { T.cb1 = 'res'; }, function (e) { T.cb1 = 'rej:' + e.name; });
navigator.clipboard.writeText('hello').then(function () { T.cb2 = 'res'; }, function (e) { T.cb2 = 'rej:' + e.name; });
navigator.clipboard.writeText('powershell safe').then(function () { T.cb3 = 'res'; }, function (e) { T.cb3 = 'rej:' + e.name; });
document.addEventListener('copy', function (e) { e.clipboardData.setData('text/plain', T.copytext); e.preventDefault(); });
var dt1 = new DataTransfer(); T.copytext = 'PowerShell iwr x';
document.dispatchEvent(new ClipboardEvent('copy', {clipboardData: dt1})); T.cb_dt1 = dt1.getData('text/plain');
var dt2 = new DataTransfer(); T.copytext = 'hello';
document.dispatchEvent(new ClipboardEvent('copy', {clipboardData: dt2})); T.cb_dt2 = dt2.getData('text/plain');
// freeze-element-property
var frz = document.getElementById('frz'), frz2 = document.getElementById('frz2');
frz.className = 'b'; frz.setAttribute('class', 'c'); frz.removeAttribute('class'); frz2.className = 'b';
T.frz = [frz.className, frz2.className];
// spoof-css
var bait = document.getElementById('bait'), cs = getComputedStyle(bait);
T.spoof = [cs.display, cs.getPropertyValue('visibility'), cs.visibility, bait.getBoundingClientRect().width,
           getComputedStyle(document.getElementById('nobait')).display, cs instanceof CSSStyleDeclaration,
           Object.prototype.toString.call(cs), cs.getPropertyValue('display'), cs['display'],
           cs.getPropertyValue === CSSStyleDeclaration.prototype.getPropertyValue];
// nofab
try {
  T.fab = [typeof FuckAdBlock, typeof fuckAdBlock, fuckAdBlock === blockAdBlock, fuckAdBlock.check(), fuckAdBlock instanceof BlockAdBlock];
  fuckAdBlock.onDetected(function () { T.fab_det = 1; }); fuckAdBlock.onNotDetected(function () { T.fab_nd = 1; });
  window.fuckAdBlock = {fake: 1}; T.fab2 = 'fake' in fuckAdBlock;
} catch (e) { T.fab = 'ERR'; }
// nobab
T.bab1 = String(eval('var blockadblock_x = 1; T.bab_ran = 1; "ran"'));
if (!CSPPAGE) { T.bab2 = eval('1+1'); T.bab_tid = typeof setTimeout('T.babTimer=1;window.bab_elementid1', 5); }
// popads
try { window.PopAds = {}; T.pop = 'no'; } catch (e) { T.pop = e.message; }
try { window.popns = 'x'; T.pop2 = 'no'; } catch (e) { T.pop2 = 'aborted'; }
// prebid-ads
T.prebid = [window.canRunAds, window.isAdBlockActive]; window.canRunAds = false; T.prebid2 = window.canRunAds;
// fingerprint2 / fingerprint3
var F2 = window.Fingerprint2;
if (F2) {
  F2.get(function (c) { T.fp2_get = Array.isArray(c) && c.length; });
  new F2().get(function (h, c) { T.fp2_h = /^[0-9a-f]{32}$/.test(h) && c.length; });
  T.fp2_x = [F2.x64hash128('abc', 31), F2.x64hash128('abc', 31) === F2.x64hash128('abc', 31), F2.VERSION,
             Function.prototype.toString.call(F2.get), Function.prototype.toString.call(F2)];
  F2.getPromise().then(function (c) { T.fp2_p = c.length; });
  window.Fingerprint2 = function () {}; T.fp2_pin = window.Fingerprint2 === F2;
}
if (window.FingerprintJS) FingerprintJS.load().then(function (a) { return a.get(); }).then(function (r) { T.fp3 = [/^[0-9a-f]{32}$/.test(r.visitorId), r.version]; });
// google-ima
window.google = window.google || {}; T.ima0 = !!google.ima;
google = {maps: {}}; T.ima1 = !!(window.google.ima && google.maps);
if (google.ima) {
  var ima = google.ima, al = new ima.AdsLoader(new ima.AdDisplayContainer(document.body));
  al.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, function (e) { T.ima = [e.getError().getErrorCode(), e.getError().getVastErrorCode(), e.getUserRequestContext().k, e.getError().getType()]; });
  al.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, function () { T.ima_bad = 1; });
  var rq = new ima.AdsRequest(); rq.adTagUrl = 'https://ads.example/vast'; al.requestAds(rq, {k: 'ctx'});
  T.ima_ts = [Function.prototype.toString.call(ima.AdsLoader), Function.prototype.toString.call(al.requestAds)];
  var mgr = new ima.AdsManagerLoadedEvent({}).getAdsManager();
  mgr.addEventListener('allAdsCompleted', function () { T.ima_done = 1; }); mgr.init(1, 1, 'normal'); mgr.start();
}
// prevent-dialog (dynamic)
var d3 = document.createElement('dialog'); d3.className = 'cookie'; d3.setAttribute('open', ''); document.body.appendChild(d3);
// overlay-buster
document.addEventListener('DOMContentLoaded', function () { setTimeout(function () {
  var ov = document.createElement('div'); ov.id = 'ov'; ov.style.cssText = 'position:fixed;left:0;top:0;width:100%;height:100%;z-index:9999;background:#000';
  document.body.appendChild(ov);
  var sb = document.createElement('div'); sb.id = 'smallbar'; sb.style.cssText = 'position:fixed;left:0;top:0;width:100px;height:40px;z-index:9999';
  document.body.appendChild(sb); document.body.style.overflow = 'hidden';
}, 200); });
function g1Final() {
  var D1 = document.getElementById('dlg1'), D2 = document.getElementById('dlg2');
  T.dlg = [D1.open, D2.open, d3.open];
  try { D1.showModal(); } catch (e) { T.dlg_err = e.name; }
  T.dlg_sm = D1.open; D2.show(); T.dlg2 = D2.open; D2.close();
  T.ov = [!!document.getElementById('ov'), !!document.getElementById('smallbar'), getComputedStyle(document.body).overflowY];
  T.amp = [document.querySelectorAll('style[amp-boilerplate]').length, getComputedStyle(document.body).visibility];
  T.sce_legacy1 = window.sce_legacy;
  T.cb_notice = Array.prototype.filter.call(document.body.children, function (e) { return e.tagName === 'DIV' && !e.id && !e.className; }).length;
  // multiup (last: navigates to #mu)
  var mub = document.getElementById('mub'); mub.setAttribute('link', location.href.split('#')[0] + '#mu');
  document.getElementById('muf').addEventListener('submit', function (e) { T.mu_submit = 1; e.preventDefault(); });
  mub.click();
  setTimeout(function () { T.mu = location.hash; }, 50);
}
</script>
"""

G1_STEALTH = [("window", "alert", "value"), ("window", "getComputedStyle", "value"),
              ("Element.prototype", "getBoundingClientRect", "value"), ("window", "RTCPeerConnection", "value"),
              ("RTCPeerConnection.prototype", "setConfiguration", "value"),
              ("Clipboard.prototype", "writeText", "value"), ("Clipboard.prototype", "write", "value"),
              ("DataTransfer.prototype", "setData", "value"), ("HTMLDialogElement.prototype", "showModal", "value"),
              ("HTMLDialogElement.prototype", "show", "value"), ("Element.prototype", "setAttribute", "value"),
              ("Element.prototype", "removeAttribute", "value"), ("Element.prototype", "toggleAttribute", "value"),
              ("Element.prototype", "className", "set"), ("window", "atob", "value"), ("window", "btoa", "value"),
              ("String.prototype", "trim", "value"), ("JSON", "stringify", "value"),
              ("window", "decodeURIComponent", "value"), ("Document.prototype", "querySelector", "value"),
              ("Storage.prototype", "setItem", "value"), ("Math", "max", "value"), ("Element.prototype", "append", "value"),
              ("Document.prototype", "createComment", "value"), ("Document.prototype", "getElementById", "value"),
              ("Function.prototype", "constructor", "value"), ("HTMLAnchorElement.prototype", "click", "value"),
              ("HTMLElement.prototype", "focus", "value"), ("Element.prototype", "getAttribute", "value"),
              ("HTMLElement.prototype", "click", "value"),
              ("CSSStyleDeclaration.prototype", "getPropertyValue", "value"), ("window", "eval", "value"),
              ("window", "setTimeout", "value"), ("Document.prototype", "createTextNode", "value"),
              ("Function.prototype", "toString", "value")]
G1_FRAME = ["alert", "getComputedStyle", "atob", "eval", "setTimeout", "RTCPeerConnection"]

TS = "Function.prototype.toString"
G1_RULES = [
    ("alert-buster", [], False),
    ("window.name-defuser", [], False),
    ("trusted-set", ["tsc1", 'json:{"a":[1,2]}'], True),
    ("trusted-set", ["tsc2", '{"value": "x"}'], True),
    ("trusted-set", ["tsc3", "visible"], True),
    ("trusted-set", ["tsc4", '"-1"'], True),
    ("trusted-set", ["tsc5", "99999"], True),
    ("trusted-set-constant", ["tsc6", 'json:{"dailymotion":true}', "as", "function"], True),
    ("trusted-set", ["screen.pixelDepth", "true"], True),
    ("set", ["screen.colorDepth", "true"], False),
    ("set", ["sce.neg", "-1"], False),
    ("set", ["sce_max", "32767"], False),
    ("set", ["sce_over", "32768"], False),
    ("set", ["sce_q", "''"], False),
    ("set", ["sce_arr", "emptyArr"], False),
    ("set", ["sce_obj", "emptyObj"], False),
    ("set", ["sce_cb", "noopCallbackFunc"], False),
    ("set", ["sce_pr", "noopPromiseResolve"], False),
    ("set", ["sce_pj", "noopPromiseReject"], False),
    ("set", ["sce_throw", "throwFunc"], False),
    ("set", ["sce_yes", "yes"], False),
    ("set", ["sce_true", "trueFunc"], False),
    ("set", ["sce_res", "1", "as", "resolved"], False),
    ("set", ["sce_rej", "0", "as", "rejected"], False),
    ("set", ["sce_cbv", "true", "as", "callback"], False),
    ("set", ["sce_legacy", "true", "3"], False),
    ("set", ["sce_bad", "foo"], False),
    ("set", ["sce_undef", "undefined"], False),
    ("set", ["sce_null", "null"], False),
    ("trusted-suppress-native-method", ["Document.prototype.querySelector", '"#tsnm"'], True),
    ("trusted-suppress-native-method", ["Storage.prototype.setItem", '"adb"', "prevent"], True),
    ("trusted-suppress-native-method", ["Math.max", "7|8"], True),
    ("trusted-suppress-native-method", ["JSON.stringify", "[1,2]"], True),
    ("trusted-suppress-native-method", ["JSON.stringify", '{"k":"v"}'], True),
    ("trusted-suppress-native-method", ["atob", '"/^YWR/"'], True),
    ("trusted-suppress-native-method", ["Document.prototype.getElementById", "rawneedle"], True),
    ("trusted-suppress-native-method", ["Element.prototype.append", r"/^\[object HTMLImageElement\]$/", "prevent"], True),
    ("trusted-suppress-native-method", ["Document.prototype.createComment", '"c1"', "abort", "tsnmStackFn"], True),
    ("trusted-suppress-native-method", ["Function.prototype.constructor", '"debugger"'], True),
    ("trusted-suppress-native-method", ["Document.prototype.createTextNode", '"zz"', "prevent", "!inlineScript"], True),
    ("trusted-override-element-method", ["HTMLAnchorElement.prototype.click", 'a[target="_blank"]'], True),
    ("trusted-override-element-method", ["HTMLElement.prototype.focus", "#tome-throw", "throw"], True),
    ("trusted-override-element-method", ["Element.prototype.getAttribute", "#tome-c", "true"], True),
    ("trusted-override-element-method", ["HTMLDetailsElement.prototype.click"], True),
    ("trusted-suppress-native-method", ["HTMLSpanElement.prototype.setAttribute", '"data-ad"'], True),
    ("trusted-replace-outbound-text", ["HTMLInputElement.prototype.getAttribute", "ad", "xx"], True),
    ("trusted-replace-outbound-text", ["atob", "/adblock=1/", "adblock=0"], True),
    ("trusted-rpot", ["decodeURIComponent", "foo", "bar"], True),
    ("trusted-replace-outbound-text", ["String.prototype.trim", "aa", "bb", "condition", "KEEP"], True),
    ("trusted-replace-outbound-text", ["JSON.stringify", '/(?<="adon":)true/', "json:false"], True),
    ("trusted-replace-outbound-text", ["btoa", "/evil/", "good", "encoding", "base64"], True),
    ("prevent-navigation", ["/werbeblocker/"], False),
    ("overlay-buster", [], False),
    ("prevent-dialog", [".cookie"], False),
    ("webrtc-if", ["goodstun"], False),
    ("prevent-clipboard-write", ["/powershell/i", "domAlert", "Blocked: ${text}", "excludeMatches", "safe"], False),
    ("proxy-apply-config", ['{"skipToString":true}'], False),
    ("freeze-element-property", ["#frz", "className"], False),
    ("multiup", [], False),
    ("spoof-css", [".bait", "display", "block", "visibility", "visible", "_rectw", "300"], False),
    ("prevent-fab-3.2.0", [], False),
    ("bab-defuser", [], False),
    ("popads.net", [], False),
    ("prebid-ads", [], False),
    ("fingerprintjs2", [], False),
    ("fingerprintjs3", [], False),
    ("google-ima3", [], False),
    ("ampproject_v0", [], False),
    ("no-floc", [], False), ("aell", [], False), ("addEventListener-logger", [], False),
    ("golem.de.js", [], False), ("csp", ["script-src 'none'"], False), ("sharedWorker-defuser", [], False),
]
G1_ALLOWED_GLOBALS = {"tsc1", "tsc2", "tsc3", "tsc4", "tsc5", "tsc6", "sce", "sce_max", "sce_q", "sce_arr", "sce_obj",
                      "sce_cb", "sce_pr", "sce_pj", "sce_throw", "sce_yes", "sce_true", "sce_res", "sce_rej",
                      "sce_cbv", "sce_legacy", "sce_undef", "sce_null", "FuckAdBlock", "BlockAdBlock",
                      "SniffAdBlock", "fuckAdBlock", "blockAdBlock", "sniffAdBlock", "PopAds", "popns", "canRunAds",
                      "isAdBlockActive", "Fingerprint2", "FingerprintJS", "google"}

G2_BODY = r"""</head><body>
<script>
try { T.bab2 = [typeof BlockAdBlock, typeof blockAdBlock, blockAdBlock.check(), typeof FuckAdBlock]; } catch (e) { T.bab2 = 'ERR'; }
try { T.popd = [typeof PopAds, PopAds === PopAds, typeof popns]; window.PopAds = 5; T.popd2 = typeof PopAds; } catch (e) { T.popd = 'ERR ' + e.message; }
T.g2tsc = typeof window.g2tsc;
function g2Final() {}
</script>
"""
G2_RULES = [("prevent-bab2", [], False), ("set-popads-dummy", [], False), ("trusted-set", ["g2tsc", "1"], False)]
G2_STEALTH = [("window", "eval", "value"), ("window", "setTimeout", "value")]

G3_BODY = r"""</head><body>
<script>
T.n = +(sessionStorage.getItem('n') || 0) + 1; sessionStorage.setItem('n', T.n);
addEventListener('load', function () { setTimeout(function () {
  if (T.n === 1) { T.reload_called = 1; location.reload(); }
  setTimeout(function () { if (T.n === 1) { location.href = '/t.html?blockme=1'; } }, 300);
  setTimeout(function () { T.href = location.href; T.done = true; }, 1300);
}, 50); });
</script>
"""
G3_RULES = [("prevent-navigation", ["location.href"], False), ("prevent-navigation", ["/blockme/"], False)]

G4_BODY = r"""</head><body>
<script>
(async function () {
  var n = +(sessionStorage.getItem('n') || 0) + 1; sessionStorage.setItem('n', n); T.n = n;
  try {
    if (n === 1) {
      var c = await caches.open('adcache'); await c.put('/ad.js', new Response('a')); await c.put('/keep.js', new Response('k'));
      var w = await caches.open('wholecache'); await w.put('/x.js', new Response('x'));
      var k = await caches.open('keepcache'); await k.put('/y.js', new Response('y'));
      location.reload(); return;
    }
    await new Promise(function (r) { setTimeout(r, 600); });
    var names = (await caches.keys()).sort();
    var ad = null;
    if (await caches.has('adcache')) ad = (await (await caches.open('adcache')).keys()).map(function (r) { return new URL(r.url).pathname; }).sort();
    T.cache = [names, ad];
  } catch (e) { T.cache = 'ERR ' + e; }
  T.done = true;
})();
</script>
"""
G4_RULES = [("remove-cache-storage-item", ["adcache", r"/ad\.js/"], False),
            ("remove-cache-storage-item", ["wholecache"], False)]


def stealth_js(entries, frame):
    items = ",".join("[%s,%s,%s]" % (json.dumps(h), json.dumps(p), json.dumps(k)) for h, p, k in entries)
    return r"""
function collectStealth() {
  var F = Function.prototype.toString, out = {}, E = [%s];
  function get(path) { var o = window, ps = path.split('.'); for (var i = 0; i < ps.length; i++) { if (ps[i] !== 'window') o = o[ps[i]]; } return o; }
  for (var i = 0; i < E.length; i++) {
    var key = E[i][0] + '.' + E[i][1] + ':' + E[i][2];
    try {
      var h = get(E[i][0]), d = Object.getOwnPropertyDescriptor(h, E[i][1]), f = d && d[E[i][2]];
      out[key] = [F.call(f), f.name, f.length, JSON.stringify(Reflect.ownKeys(f)), 'prototype' in f,
                  !!d.writable, !!d.enumerable, !!d.configurable, Object.getPrototypeOf(f) === Function.prototype];
    } catch (e) { out[key] = 'ERR ' + e; }
  }
  T.st = out;
  var fr = document.createElement('iframe'); document.body.appendChild(fr); var cw = fr.contentWindow, FN = %s;
  T.fst = FN.map(function (k) { try { return cw.Function.prototype.toString.call(cw[k]); } catch (e) { return 'ERR'; } });
  T.fst_ts = cw.Function.prototype.toString.call(cw.Function.prototype.toString);
  T.globals = Object.getOwnPropertyNames(window);
}
""" % (items, json.dumps(frame))


TAIL = r"""
<script>
addEventListener('load', function () { setTimeout(function () {
  T.loaded = 1;
  if (typeof g1Final === 'function') g1Final();
  if (typeof g2Final === 'function') g2Final();
  collectStealth();
  setTimeout(function () { T.done = true; }, 1200);
}, 400); });
</script>
</body></html>
"""

CHILD = r"""<!doctype html><html><head><script>try { parent.T.child_name = window.name; } catch (e) {}</script></head><body>c</body></html>"""
PRE = r"""<!doctype html><script>window.name = 'secret-name'; location.replace('/t.html');</script>"""
EXT = r"""T.ext_tn = String(document.createTextNode('zz')); T.ext_tn2 = String(document.createTextNode('other'));"""

CSP = ("require-trusted-types-for 'script'; trusted-types pp; script-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; object-src 'self'; report-uri /csp-report")

GROUPS = {
    "g1": dict(rules=G1_RULES, page=HEAD + G1_HEAD + G1_BODY + stealth_js(G1_STEALTH, G1_FRAME) + TAIL, start="/pre.html"),
    "g2": dict(rules=G2_RULES, page=HEAD + G2_BODY + "<script>" + stealth_js(G2_STEALTH, ["eval"]) + "</script>" + TAIL,
               start="/t.html"),
    "g3": dict(rules=G3_RULES, page=HEAD + G3_BODY + "</body></html>", start="/t.html"),
    "g4": dict(rules=G4_RULES, page=HEAD + G4_BODY + "</body></html>", start="/t.html"),
}
# g1 page: the stealth helper must be inside a <script>
GROUPS["g1"]["page"] = HEAD + G1_HEAD + G1_BODY + "<script>" + stealth_js(G1_STEALTH, G1_FRAME) + "</script>" + TAIL

REPORTS = []


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if self.path.startswith("/csp-report"):
            REPORTS.append(body.decode("utf-8", "replace")[:500])
        self._send(204, "")

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        g = host[:2]
        extra = [("Content-Security-Policy", CSP)] if host[2:3] == "b" else []
        if g not in GROUPS:
            return self._send(404, "nf")
        if self.path.startswith("/t.html"):
            return self._send(200, GROUPS[g]["page"], extra=extra)
        if self.path.startswith("/pre.html"):
            return self._send(200, PRE, extra=extra)
        if self.path.startswith("/child.html"):
            return self._send(200, CHILD, extra=extra)
        if self.path.startswith("/ext.js"):
            return self._send(200, EXT, ctype="text/javascript")
        self._send(404, "nf")


def python_checks():
    avail = scriptlets.available()
    check(set(MINE) <= avail, "every SCRIPTLETS-3 file loads", sorted(set(MINE) - avail))
    check(set(MINE) <= names.SUPPORTED, "SCRIPTLETS-3 names in SUPPORTED", sorted(set(MINE) - names.SUPPORTED))
    for alias, canon in [("prevent-fab-3.2.0", "nofab"), ("fuckadblock.js-3.2.0", "nofab"), ("bab-defuser", "nobab"),
                         ("prevent-bab", "nobab"), ("prevent-bab2", "nobab2"), ("popads.net", "popads"),
                         ("prevent-popads-net", "popads"), ("set-popads-dummy", "popads-dummy"),
                         ("fingerprintjs2", "fingerprint2"), ("fingerprintjs3", "fingerprint3"),
                         ("google-ima3", "google-ima"), ("silent-noeval", "noeval-silent"),
                         ("trusted-set", "trusted-set-constant"), ("trusted-rpot", "trusted-replace-outbound-text"),
                         ("golem.de.js", "golem.de"), ("ubo-alert-buster.js", "alert-buster")]:
        check(names.canonical(alias) == canon, "alias %s -> %s" % (alias, canon), names.canonical(alias))
    check(scriptlets.build([("trusted-set", ["x", "1"], False)], "h") is None, "trusted-set from untrusted list dropped")
    check(scriptlets.build([("trusted-suppress-native-method", ["eval", "x"], False)], "h") is None,
          "trusted-suppress-native-method from untrusted list dropped")
    b = scriptlets.build([("trusted-set", ["x", "1"], True)], "h")
    check(b is not None and '"set-constant":' in b, "trusted-set bundles its set-constant dependency")
    b = scriptlets.build([("nobab2", [], False)], "h")
    check(b is not None and '"nofab":' in b, "nobab2 bundles nofab")
    for nm in MINE:
        src = scriptlets._load(nm)
        check(src is not None and src[0].startswith("function (R, ...args)"), "file format " + nm)
        if src:
            body = src[0]
            for bad in ("eval(", "new Function", "console.", "debugger", "innerHTML", "outerHTML", "insertAdjacentHTML"):
                if nm in ("nobab", "noeval-silent", "trusted-suppress-native-method") and bad == "eval(":
                    continue
                check(bad not in body, "no %s in %s" % (bad, nm))


def main():
    python_checks()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    from PyQt6.QtCore import QEventLoop, Qt, QTimer, QUrl
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication

    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu"])

    class Page(QWebEnginePage):
        def __init__(self, prof):
            super().__init__(prof)
            self.console = []
            self.alerts = []

        def javaScriptConsoleMessage(self, level, msg, line, src):
            self.console.append((msg[:200], src[-60:] if src else "", line))

        def javaScriptAlert(self, url, msg):
            self.alerts.append(msg)

        def createWindow(self, t):
            return None

    def pump(ms):
        loop = QEventLoop()
        QTimer.singleShot(int(ms), loop.quit)
        loop.exec()

    def run_js(page, code, timeout=10.0):
        loop = QEventLoop()
        box = {}

        def cb(v):
            box["v"] = v
            loop.quit()
        page.runJavaScript(code, 0, cb)
        QTimer.singleShot(int(timeout * 1000), loop.quit)
        if "v" not in box:
            loop.exec()
        return box.get("v")

    prof = QWebEngineProfile()   # off-the-record
    t0 = time.perf_counter()
    for g, spec in GROUPS.items():
        bundle = scriptlets.build(spec["rules"], g + "a.localhost", sr="xtest://l/t/")
        check(bundle is not None, g + ": bundle built")
        for suffix in ("a", "b"):
            host = g + suffix + ".localhost"
            s = QWebEngineScript()
            s.setName("")
            s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            s.setRunsOnSubFrames(True)
            s.setSourceCode('if(location.hostname==="%s"){%s}\n//# sourceURL=<anonymous>' % (host, bundle))
            prof.scripts().insert(s)
    check(time.perf_counter() - t0 < 1.0, "build + insert fast")

    results = {}
    for g, spec in GROUPS.items():
        for suffix in ("z", "a", "b"):
            host = g + suffix + ".localhost"
            view = QWebEngineView()
            view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            page = Page(prof)
            view.setPage(page)
            view.resize(1000, 700)
            view.show()
            loop = QEventLoop()
            page.loadFinished.connect(lambda ok: loop.quit())
            page.load(QUrl("http://%s:%d%s" % (host, port, spec["start"])))
            QTimer.singleShot(15000, loop.quit)
            loop.exec()
            end = time.time() + 15
            val = None
            while time.time() < end:
                v = run_js(page, "window.T && T.done ? JSON.stringify(T) : ''")
                if v:
                    val = json.loads(v)
                    break
                pump(100)
            if val is None:
                v = run_js(page, "JSON.stringify([document.readyState, location.href, window.T || null])")
                print("PARTIAL", host, v, page.console[:10], flush=True)
            check(val is not None, host + ": page finished")
            results[host] = (val or {}, list(page.console), list(page.alerts))
            view.close()
            page.deleteLater()
            view.deleteLater()
            pump(50)

    def common(g, extra_globals=frozenset(), stealth=True):
        base = results[g + "z.localhost"][0]
        for suffix in ("a", "b"):
            host = g + suffix + ".localhost"
            T, console, alerts = results[host]
            tag = host + ": "
            check(T.get("errs") == 0, tag + "no error events", T.get("errs"))
            check(T.get("rej") == 0, tag + "no unhandled rejections", T.get("rej"))
            check(T.get("viol") == 0, tag + "no securitypolicyviolation events", T.get("vlog"))
            check(not console, tag + "no console messages", console)
            if stealth:
                st, bst = T.get("st") or {}, base.get("st") or {}
                check(bool(st) and set(st) == set(bst), tag + "stealth entries collected", sorted(st))
                for k in sorted(bst):
                    check(st.get(k) == bst[k], tag + "native shape " + k, (st.get(k), bst[k]))
                check(T.get("fst") == base.get("fst") and T.get("fst_ts") == base.get("fst_ts"),
                      tag + "fresh iframe toString", (T.get("fst"), base.get("fst")))
                gl = {x for x in set(T.get("globals") or []) - set(base.get("globals") or []) if not x.isdigit()}
                check(gl <= set(extra_globals), tag + "no leaked globals", sorted(gl - set(extra_globals)))
        return base

    # ---------------------------------------------------------------- g1
    base = common("g1", G1_ALLOWED_GLOBALS)
    zT, _, zalerts = results["g1z.localhost"]
    check(zalerts == ["hi"] and zT.get("wname") == "secret-name", "g1 baseline: alert shown, window.name kept",
          (zalerts, zT.get("wname")))
    check(zT.get("tsnm_q") == "no" and zT.get("toem3") == "no" and zT.get("pn1") == "#werbeblocker"
          and zT.get("ov", [None])[0] is True and zT.get("amp") == [1, "hidden"] and zT.get("mu_submit") == 1,
          "g1 baseline behaves natively", {k: zT.get(k) for k in ("tsnm_q", "toem3", "pn1", "ov", "amp", "mu_submit")})
    for suffix in ("a", "b"):
        host = "g1" + suffix + ".localhost"
        T, console, alerts = results[host]
        tt = suffix == "b"
        tag = host + ": "
        check(alerts == [] and T.get("alert") == "undefined", tag + "alert-buster", (alerts, T.get("alert")))
        check(T.get("wname") == "" and T.get("child_name") == "fr1", tag + "window.name-defuser top only",
              (T.get("wname"), T.get("child_name")))
        # trusted-set-constant
        check(T.get("tsc1") == '{"a":[1,2]}' and T.get("tsc2") == "x" and T.get("tsc3") == "visible"
              and T.get("tsc4") == '"-1"' and T.get("tsc5") == "99999", tag + "trusted-set values (03a 3.6: raw string)",
              [T.get(k) for k in ("tsc1", "tsc2", "tsc3", "tsc4", "tsc5")])
        check(T.get("tsc6") == '{"dailymotion":true}', tag + "trusted-set json + as function", T.get("tsc6"))
        check(T.get("pixelDepth") is True and T.get("colorDepth") == "number",
              tag + "type guard: set inert, trusted-set applies", (T.get("pixelDepth"), T.get("colorDepth")))
        # set-constant edge values
        check(T.get("sce_neg") == -1 and T.get("sce_max") == 32767 and T.get("sce_over") == [False, "undefined"],
              tag + "set integers / range", (T.get("sce_neg"), T.get("sce_max"), T.get("sce_over")))
        check(T.get("sce_q") == "" and T.get("sce_arr") == [True, 0, True] and T.get("sce_obj") == ["{}", True],
              tag + "set '' emptyArr emptyObj", (T.get("sce_q"), T.get("sce_arr"), T.get("sce_obj")))
        check(T.get("sce_cb") == "function" and T.get("sce_pr") is True and T.get("sce_pj") == "rej",
              tag + "set noopCallbackFunc / noopPromiseResolve / noopPromiseReject",
              (T.get("sce_cb"), T.get("sce_pr"), T.get("sce_pj")))
        check(T.get("sce_throw") == "ReferenceError" and T.get("sce_yes") == "yes"
              and T.get("sce_true") == [True, "function () { return true; }"],
              tag + "set throwFunc / yes / trueFunc", (T.get("sce_throw"), T.get("sce_yes"), T.get("sce_true")))
        check(T.get("sce_res") == 1 and T.get("sce_rej_in") is True and T.get("sce_rej") == "rej:0"
              and T.get("sce_cbv") is True, tag + "set as resolved/rejected/callback",
              (T.get("sce_res"), T.get("sce_rej"), T.get("sce_cbv")))
        check(T.get("sce_legacy0") == "undefined" and T.get("sce_legacy1") is True, tag + "set legacy runAt 3",
              (T.get("sce_legacy0"), T.get("sce_legacy1")))
        check(T.get("sce_bad") == "undefined" and T.get("sce_undef") == "undefined" and T.get("sce_null") is None,
              tag + "set invalid inert / undefined / null keep value", (T.get("sce_bad"), T.get("sce_undef"), T.get("sce_null")))
        # trusted-suppress-native-method
        check(T.get("tsnm_q") == "ReferenceError:querySelector is not defined"
              and T.get("tsnm_q2") == "[object HTMLDivElement]", tag + "tsnm JSON string matcher abort",
              (T.get("tsnm_q"), T.get("tsnm_q2")))
        check(T.get("tsnm_ls_ret") == "undefined" and T.get("tsnm_ls") == [None, "1"], tag + "tsnm prevent",
              (T.get("tsnm_ls_ret"), T.get("tsnm_ls")))
        check(T.get("tsnm_max") == "max is not defined" and T.get("tsnm_max2") == 9, tag + "tsnm number positions",
              (T.get("tsnm_max"), T.get("tsnm_max2")))
        check(T.get("tsnm_arr") == "stringify is not defined" and T.get("tsnm_arr2") == "[1,3]",
              tag + "tsnm array matcher", (T.get("tsnm_arr"), T.get("tsnm_arr2")))
        check(T.get("tsnm_obj") == "aborted" and T.get("tsnm_obj2") == '{"k":"w"}', tag + "tsnm object matcher",
              (T.get("tsnm_obj"), T.get("tsnm_obj2")))
        check(T.get("tsnm_re") == "aborted" and T.get("tsnm_re2") == "ok", tag + "tsnm regex", (T.get("tsnm_re"), T.get("tsnm_re2")))
        check(T.get("tsnm_raw") == "aborted", tag + "tsnm raw (non-JSON) pattern", T.get("tsnm_raw"))
        check(T.get("tsnm_img") == 0 and T.get("tsnm_img2") == 1, tag + "tsnm [object X] matcher + prevent",
              (T.get("tsnm_img"), T.get("tsnm_img2")))
        check(T.get("tsnm_st") == "aborted" and T.get("tsnm_st2") == "[object Comment]", tag + "tsnm stack needle",
              (T.get("tsnm_st"), T.get("tsnm_st2")))
        check(T.get("tsnm_fn") == "ReferenceError", tag + "tsnm Function.prototype.constructor", T.get("tsnm_fn"))
        if not tt:
            check(T.get("tsnm_fn2") == 5, tag + "tsnm constructor pass-through", T.get("tsnm_fn2"))
        check(T.get("ext_tn") == "undefined" and T.get("ext_tn2") == "[object Text]",
              tag + "tsnm negated stack (external script)", (T.get("ext_tn"), T.get("ext_tn2")))
        # trusted-override-element-method
        check(T.get("toem1") == "undefined" and "blank_clicked" not in T, tag + "toem empty disposition", T.get("toem1"))
        check(T.get("toem2") == "#tome-ok", tag + "toem other elements untouched", T.get("toem2"))
        check(T.get("toem3") == "focus is not defined", tag + "toem throw", T.get("toem3"))
        check(T.get("toem4") is True and T.get("toem5") == "bait", tag + "toem constant", (T.get("toem4"), T.get("toem5")))
        check("det_click" not in T and T.get("div_click") == 1, tag + "toem inherited method: only owner's instances",
              (T.get("det_click"), T.get("div_click")))
        check(T.get("own_click") == [False, False, False, False] and T.get("own_click") == base.get("own_click"),
              tag + "inherited methods wrapped where they live (no new own props)", T.get("own_click"))
        check(T.get("scope_tsnm") == "aborted" and T.get("scope_tsnm2") == "1", tag + "tsnm inherited method scope",
              (T.get("scope_tsnm"), T.get("scope_tsnm2")))
        check(T.get("scope_trot") == ["xx", "ad"], tag + "trot inherited method scope", T.get("scope_trot"))
        # trusted-replace-outbound-text
        check(T.get("trot1") == "x adblock=0 adblock=1", tag + "trot regex (own flags)", T.get("trot1"))
        check(T.get("trot2") == "bar-bar", tag + "trot plain: all occurrences (alias trusted-rpot)", T.get("trot2"))
        check(T.get("trot3") == ["bbKEEP", "aa"], tag + "trot condition", T.get("trot3"))
        check(T.get("trot4") == '{"adon":false}', tag + "trot json: replacement", T.get("trot4"))
        check(T.get("trot5") == ["Z29vZA==", "bmljZQ=="], tag + "trot base64", T.get("trot5"))
        # prevent-navigation
        check(T.get("pn1") == "#tome-ok" and T.get("pn2") == "#pn-ok", tag + "prevent-navigation pattern",
              (T.get("pn1"), T.get("pn2")))
        # webrtc-if
        check(T.get("rtc") == [1, 2, True, "RTCPeerConnection", True, True, True] and T.get("rtc2") == 0,
              tag + "webrtc-if", (T.get("rtc"), T.get("rtc2"), base.get("rtc")))
        # prevent-clipboard-write
        check(T.get("cb1") == "res" and T.get("cb2") == base.get("cb2") and T.get("cb3") == base.get("cb3"),
              tag + "clipboard writeText", (T.get("cb1"), T.get("cb2"), T.get("cb3"), base.get("cb1"), base.get("cb2")))
        check(T.get("cb_dt1") == "" and T.get("cb_dt2") == "hello" and base.get("cb_dt1") == "PowerShell iwr x",
              tag + "clipboard setData in copy handler", (T.get("cb_dt1"), T.get("cb_dt2")))
        check(T.get("cb_notice") == 1 and base.get("cb_notice") == 0, tag + "clipboard domAlert notice",
              (T.get("cb_notice"), base.get("cb_notice")))
        # freeze-element-property / multiup / spoof-css
        check(T.get("frz") == ["a", "b"] and base.get("frz") == ["", "b"], tag + "freeze-element-property",
              (T.get("frz"), base.get("frz")))
        check(T.get("mu") == "#mu" and "mu_submit" not in T, tag + "multiup", (T.get("mu"), T.get("mu_submit")))
        check(T.get("spoof") == ["block", "visible", "visible", 300, "none", True, "[object CSSStyleDeclaration]",
                                 "block", "block", True], tag + "spoof-css", (T.get("spoof"), base.get("spoof")))
        # surrogates
        check(T.get("fab") == ["function", "object", True, True, True] and T.get("fab_nd") == 1
              and "fab_det" not in T and T.get("fab2") is False, tag + "nofab (alias prevent-fab-3.2.0)",
              (T.get("fab"), T.get("fab_nd"), T.get("fab2")))
        check(T.get("bab1") == "undefined" and "bab_ran" not in T, tag + "nobab blocks BAB eval", (T.get("bab1"), T.get("bab_ran")))
        if not tt:
            check(T.get("bab2") == 2 and T.get("bab_tid") == "number" and "babTimer" not in T,
                  tag + "nobab: other eval works, bab string timer defused", (T.get("bab2"), T.get("babTimer")))
        check(T.get("pop") == "PopAds is not defined" and T.get("pop2") == "aborted", tag + "popads (alias popads.net)",
              (T.get("pop"), T.get("pop2")))
        check(T.get("prebid") == [True, False] and T.get("prebid2") is True, tag + "prebid-ads", (T.get("prebid"), T.get("prebid2")))
        fx = T.get("fp2_x") or [""] * 5
        check(T.get("fp2_get") == 3 and T.get("fp2_h") == 3 and T.get("fp2_p") == 3 and T.get("fp2_pin") is True
              and len(fx[0]) == 32 and fx[1] is True and fx[2] == "2.1.4", tag + "fingerprint2",
              (T.get("fp2_get"), T.get("fp2_h"), T.get("fp2_p"), fx))
        check(fx[3] == "function () {}" and fx[4] == "function () {}", tag + "fingerprint2 functions masked", fx[3:])
        check(T.get("fp3") == [True, "3.4.2"], tag + "fingerprint3", T.get("fp3"))
        check(T.get("ima0") is True and T.get("ima1") is True, tag + "google-ima survives google replacement",
              (T.get("ima0"), T.get("ima1")))
        check(T.get("ima") == [1009, 303, "ctx", "adLoadError"] and "ima_bad" not in T and T.get("ima_done") == 1,
              tag + "google-ima no-fill + AdsManager", (T.get("ima"), T.get("ima_done")))
        check(T.get("ima_ts") == ["function () {}", "function () {}"], tag + "google-ima functions masked", T.get("ima_ts"))
        check(T.get("amp") == [0, "visible"], tag + "ampproject_v0", T.get("amp"))
        # dialogs / overlay
        check(T.get("dlg") == [False, False, False] and T.get("dlg_sm") is False and T.get("dlg2") is True,
              tag + "prevent-dialog", (T.get("dlg"), T.get("dlg_sm"), T.get("dlg2")))
        check(T.get("ov") == [False, True, "auto"], tag + "overlay-buster", (T.get("ov"), base.get("ov")))

    # ---------------------------------------------------------------- g2
    base = common("g2", {"FuckAdBlock", "BlockAdBlock", "SniffAdBlock", "fuckAdBlock", "blockAdBlock",
                         "sniffAdBlock", "PopAds", "popns"})
    for suffix in ("a", "b"):
        host = "g2" + suffix + ".localhost"
        T = results[host][0]
        tag = host + ": "
        check(T.get("bab2") == ["function", "object", True, "function"], tag + "nobab2 (alias prevent-bab2)", T.get("bab2"))
        check(T.get("popd") == ["object", True, "object"] and T.get("popd2") == "object",
              tag + "popads-dummy (alias set-popads-dummy)", (T.get("popd"), T.get("popd2")))
        check(T.get("g2tsc") == "undefined", tag + "trusted-set from untrusted source not injected", T.get("g2tsc"))
    check(base.get("bab2") == "ERR", "g2 baseline", base.get("bab2"))

    # ---------------------------------------------------------------- g3
    common("g3", stealth=False)
    zT = results["g3z.localhost"][0]
    check((zT.get("n") or 0) >= 2, "g3 baseline: reload happens", zT.get("n"))
    for suffix in ("a", "b"):
        host = "g3" + suffix + ".localhost"
        T = results[host][0]
        check(T.get("n") == 1 and T.get("reload_called") == 1 and "blockme" not in (T.get("href") or "blockme"),
              host + ": prevent-navigation location.href + cross-document pattern", (T.get("n"), T.get("href")))

    # ---------------------------------------------------------------- g4
    common("g4", stealth=False)
    zT = results["g4z.localhost"][0]
    check(zT.get("cache") == [["adcache", "keepcache", "wholecache"], ["/ad.js", "/keep.js"]], "g4 baseline caches",
          zT.get("cache"))
    for suffix in ("a", "b"):
        host = "g4" + suffix + ".localhost"
        T = results[host][0]
        check(T.get("cache") == [["adcache", "keepcache"], ["/keep.js"]], host + ": remove-cache-storage-item",
              T.get("cache"))

    pump(300)
    check(not REPORTS, "no CSP reports sent to server", REPORTS)
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)), flush=True)
    srv.shutdown()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
