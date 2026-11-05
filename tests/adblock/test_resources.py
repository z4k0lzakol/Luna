# Testy adblock/resources.py + adblock/res/* (surrogates).
# Uruchomienie: python -I tests/adblock/test_resources.py [--no-qt]
# Część 1: czysty Python (nazwy, aliasy, MIME, pliki binarne, known_library, default_for).
# Część 2: prawdziwy QtWebEngine – każdy zasób serwowany przez przekierowanie z interceptora na losowy
#          schemat własny (SecureScheme|ContentSecurityPolicyIgnored|CorsEnabled|FetchApiAllowed),
#          strona z CSP bez 'unsafe-eval' i z require-trusted-types-for; sprawdzane API, wywołania callbacków,
#          brak komunikatów konsoli, brak błędów i brak nieoczekiwanych zmiennych globalnych.
import importlib.util
import json
import os
import re
import secrets
import struct
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES_DIR = os.path.join(REPO, "adblock", "res")

_spec = importlib.util.spec_from_file_location("luna_adblock_resources", os.path.join(REPO, "adblock", "resources.py"))
res = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(res)

PASS = []
FAIL = []


def check(name, cond, info=""):
    (PASS if cond else FAIL).append(name)
    if not cond:
        print("FAIL", name, info, flush=True)


# ----------------------------------------------------------------------------- część 1
def unit_tests():
    RT = dict(DOCUMENT=1, SUBDOCUMENT=2, STYLESHEET=3, SCRIPT=4, IMAGE=5, FONT=6, OBJECT=7, MEDIA=8, XHR=9,
              PING=10, WEBSOCKET=11, OTHER=12, POPUP=13)
    # wszystkie kanoniczne nazwy ładują się
    for n in res._TABLE:
        r = res.get(n)
        check("get:" + n, r is not None and isinstance(r[1], bytes) and r[0], r)
    # aliasy
    for a, c in res.ALIASES.items():
        check("alias:" + a, res.canonical(a) == c and res.get(a) == res.get(c) and c in res._TABLE)
    check("names-has-aliases", {"noopjs", "nooptext", "noopframe", "noopmp3-0.1s", "noopmp4-1s", "google-ima3",
                                "noop-vmap1.0.xml", "googletagservices.com/gpt.js", "1x1-transparent.gif",
                                "none", "empty", "fuckadblock.js-3.2.0"} <= res.NAMES)
    check("none", res.get("none") is None and res.canonical("none") == "none")
    check("unknown", res.get("does-not-exist.js") is None and res.canonical("x") is None and res.get("") is None)
    check("priority-suffix", res.canonical("noop.js:5") == "noop.js" and res.canonical("noopjs:-1") == "noop.js")
    check("abp-resource", res.canonical("abp-resource:blank-js") == "noop.js")
    check("no-path-names", res.get("../resources.py") is None and res.get("_gen.py") is None)
    # MIME
    mimes = {"noop.js": "application/javascript", "noop.css": "text/css", "noop.html": "text/html",
             "noop.txt": "text/plain", "1x1.gif": "image/gif", "2x2.png": "image/png",
             "noop-0.1s.mp3": "audio/mpeg", "noop-1s.mp4": "video/mp4", "noop.json": "application/json",
             "noop-vast3.xml": "application/xml", "google-ima.js": "application/javascript"}
    for n, m in mimes.items():
        check("mime:" + n, res.get(n)[0] == m, res.get(n)[0])
    check("noop.json", json.loads(res.get("noop.json")[1]) == {})
    # XML poprawny
    for n, root, ver in (("noop-vast2.xml", "VAST", "2.0"), ("noop-vast3.xml", "VAST", "3.0"),
                         ("noop-vast4.xml", "VAST", "4.0"), ("noop-vmap1.xml", "VMAP", "1.0")):
        el = ET.fromstring(res.get(n)[1])
        check("xml:" + n, el.tag.endswith(root) and el.get("version") == ver and len(el) == 0)
    # obrazy: wymiary
    g = res.get("1x1.gif")[1]
    check("gif-dims", g[:6] == b"GIF89a" and struct.unpack("<HH", g[6:10]) == (1, 1) and len(g) == 43)
    for n, wh in (("2x2.png", (2, 2)), ("3x2.png", (3, 2)), ("32x32.png", (32, 32))):
        b = res.get(n)[1]
        check("png-dims:" + n, b[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", b[16:24]) == wh
              and b[25] == 6)
    # MP3: ramki po 144 B
    for n, frames in (("noop-0.1s.mp3", 3), ("noop-0.5s.mp3", 14)):
        b = res.get(n)[1]
        check("mp3:" + n, len(b) == 144 * frames and all(b[i:i + 2] == b"\xff\xfb" for i in range(0, len(b), 144)))
    v = res.get("noop-1s.mp4")[1]
    check("mp4-vp9", v[4:8] == b"ftyp" and b"vp09" in v and b"avc1" not in v)
    check("webm", res.get("noop-1s.webm")[1][:4] == b"\x1a\x45\xdf\xa3")
    # _gen.py odtwarza pliki bajt w bajt
    p = subprocess.run([sys.executable, "-I", os.path.join(RES_DIR, "_gen.py"), "--check"], capture_output=True,
                       text=True)
    check("gen-check", p.returncode == 0, p.stdout + p.stderr)
    # każdy plik w res/ jest używany
    used = {src for _, src in res._TABLE.values() if isinstance(src, str)} | {"_gen.py"}
    stray = [f for f in os.listdir(RES_DIR) if f not in used and not f.startswith("__")]
    check("no-stray-files", not stray, stray)
    # higiena JS: bez console, bez komentarzy, bez eval/Function/string timers/innerHTML/document.write
    for n, (mime, src) in res._TABLE.items():
        if mime != "application/javascript":
            continue
        js = res.script_body(n)
        check("js-ascii:" + n, all(ord(c) < 128 for c in js))
        check("js-no-console:" + n, "console" not in js)
        check("js-no-comments:" + n, not re.search(r"(^|\s)//|/\*", js))
        check("js-no-dyncode:" + n, not re.search(r"\bnew Function\b|\bFunction\(|innerHTML|outerHTML|"
                                                  r"document\.write|insertAdjacentHTML|\beval\(", js))
        check("js-no-luna:" + n, "luna" not in js.lower() and "ublock" not in js.lower())
    check("script_body-nonjs", res.script_body("2x2.png") is None and res.script_body("nofab.js").startswith("("))
    # default_for
    D = res.default_for
    check("default:script", D(RT["SCRIPT"]) == "noop.js")
    check("default:frame", D(RT["SUBDOCUMENT"]) == "noop.html")
    check("default:css", D(RT["STYLESHEET"]) == "noop.css")
    check("default:img", D(RT["IMAGE"]) == "2x2.png" and D(RT["IMAGE"], "https://a.b/x.gif?1") == "2x2.png")
    check("default:favicon", D(RT["IMAGE"], "https://a.b/favicon.ico") == "32x32.png")
    check("default:media-audio", D(RT["MEDIA"], "https://a.b/x.MP3?x=1") == "noop-0.1s.mp3")
    check("default:media-video", D(RT["MEDIA"], "https://a.b/v.mp4") == "noop-1s.mp4" and D(RT["MEDIA"]) == "noop-1s.mp4")
    check("default:xhr", D(RT["XHR"]) == "noop.txt")
    for k in ("DOCUMENT", "FONT", "OBJECT", "PING", "WEBSOCKET", "OTHER", "POPUP"):
        check("default:none:" + k, D(RT[k]) is None)
    # known_library
    K = res.known_library
    cases = {
        "https://securepubads.g.doubleclick.net/tag/js/gpt.js": "googletagservices_gpt.js",
        "https://www.googletagservices.com/tag/js/gpt.js?x=1": "googletagservices_gpt.js",
        "https://pagead2.googlesyndication.com/tag/js/gpt.js": "googletagservices_gpt.js",
        "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1": "googlesyndication_adsbygoogle.js",
        "https://imasdk.googleapis.com/js/sdkloader/ima3.js": "google-ima.js",
        "https://imasdk.googleapis.com/js/sdkloader/ima3_debug.js": "google-ima.js",
        "https://www.google-analytics.com/analytics.js": "google-analytics_analytics.js",
        "https://ssl.google-analytics.com/ga.js": "google-analytics_ga.js",
        "https://stats.g.doubleclick.net/dc.js": "google-analytics_ga.js",
        "https://www.google-analytics.com/cx/api.js?experiment=1": "google-analytics_cx_api.js",
        "https://www.googletagmanager.com/gtm.js?id=GTM-1": "googletagmanager_gtm.js",
        "https://www.googletagmanager.com/gtag/js?id=G-1": "googletagmanager_gtm.js",
        "https://c.amazon-adsystem.com/aax2/apstag.js": "amazon_apstag.js",
        "https://c.amazon-adsystem.com/aax2/amzn_ads.js": "amazon_ads.js",
        "https://static.doubleclick.net/instream/ad_status.js": "doubleclick_instream_ad_status.js",
        "https://sb.scorecardresearch.com/beacon.js": "scorecardresearch_beacon.js",
        "https://widgets.outbrain.com/outbrain.js": "outbrain-widget.js",
        "https://cdn.ampproject.org/v0.js": "ampproject_v0.js",
        "https://example.com/js/fuckadblock.js": "nofab.js",
        "https://example.com/blockadblock.min.js?v=3": "nofab.js",
        "https://cdn.example.org/static/prebid-ads.js": "prebid-ads.js",
        "https://example.com/ads.js": "prebid-ads.js",
        "https://openfpcdn.io/fingerprintjs/v3": "fingerprint3.js",
        "https://x.test/fingerprint2.min.js": "fingerprint2.js",
        "https://USER@WWW.GOOGLE-ANALYTICS.COM:443/analytics.js": "google-analytics_analytics.js",
        "https://example.com/analytics.js": None,
        "https://example.com/gpt.js": None,
        "https://evil-doubleclick.net/tag/js/gpt.js": None,
        "https://example.com/tag/js/gpt.js": None,
        "https://www.google-analytics.com/api.js": None,
        "https://www.googletagmanager.com/js": None,
        "https://example.com/": None,
        "not a url": None,
    }
    for u, exp in cases.items():
        check("known:" + u, K(u) == exp, K(u))
    check("known:rtype", K("https://www.google-analytics.com/analytics.js", RT["XHR"]) is None
          and K("https://www.google-analytics.com/analytics.js", RT["SCRIPT"]) == "google-analytics_analytics.js")
    # wydajność (wywoływane dla każdego zablokowanego żądania)
    urls = list(cases) * 200
    t = time.perf_counter()
    for u in urls:
        K(u)
    per = (time.perf_counter() - t) / len(urls) * 1e6
    check("known:perf<15us", per < 15, f"{per:.2f} us")
    print(f"known_library: {per:.2f} us/call", flush=True)


# ----------------------------------------------------------------------------- część 2 (Qt)
HEAD = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<script>var __snap=Object.getOwnPropertyNames(window);var __R={{}};var __errs=[];
window.addEventListener('error',function(e){{__errs.push(String(e.message))}});
document.addEventListener('securitypolicyviolation',function(e){{__errs.push('CSP:'+e.violatedDirective)}});
function __sleep(ms){{return new Promise(function(r){{setTimeout(r,ms)}})}}</script>
"""
TAIL = """<script>
async function __t(){{ {check} }}
window.addEventListener('load',function(){{setTimeout(async function(){{
 try{{await __t();}}catch(e){{__R.exc=String(e&&e.stack||e);}}
 var allowed=['__snap','__R','__errs','__sleep','__t','__done'].concat({allowed});
 __R.leak=Object.getOwnPropertyNames(window).filter(function(k){{return !/^\\d+$/.test(k)&&__snap.indexOf(k)<0&&allowed.indexOf(k)<0}});
 __R.errs=__errs; window.__done=JSON.stringify(__R);
}},30)}});
</script></body></html>"""
CSP_STRICT = "script-src 'unsafe-inline' https:; require-trusted-types-for 'script'"
CSP_EVAL = "script-src 'unsafe-inline' 'unsafe-eval' https:"


def page_html(src, pre="", body="", check="", allowed=(), csp=CSP_STRICT, is_async=False):
    s = f'<script {"async " if is_async else ""}src="{src}" onload="__R.load=1" onerror="__R.load=-1"></script>' if src else ""
    return (HEAD.format(csp=csp) + pre + s + "</head><body>" + body
            + TAIL.format(check=check, allowed=json.dumps(list(allowed))))


CASES = []


def case(name, src, expect, **kw):
    CASES.append((name, src, kw, expect))


def define_cases():
    case("gpt", "https://securepubads.g.doubleclick.net/tag/js/gpt.js",
         pre="""<script>window.googletag=window.googletag||{cmd:[]};
googletag.cmd.push(function(){__R.q1this=(this===window);
 var s=googletag.defineSlot('/123/x',[300,250],'div-gpt-1').addService(googletag.pubads()).setTargeting('k',['a','b']);
 googletag.pubads().enableSingleRequest();googletag.pubads().collapseEmptyDivs();
 googletag.pubads().addEventListener('slotRequested',function(e){__R.req=(e.slot===s)});
 googletag.pubads().addEventListener('slotRenderEnded',function(e){__R.ev=[e.isEmpty,e.slot===s,e.serviceName,e.size]});
 googletag.enableServices();__R.q1=1;});
googletag.cmd.push(function(){throw new Error('x')},function(){__R.q1b=1});</script>""",
         body="""<div id="div-gpt-1" style="width:300px;height:250px"></div>
<script>googletag.cmd.push(function(){googletag.display('div-gpt-1');__R.disp=1})</script>""",
         check="""var r=googletag.cmd.push(function(){__R.q2=1});__R.pushRet=typeof r;
var p=googletag.pubads();var s=p.getSlots()[0];
__R.api=[typeof googletag.defineSlot,typeof googletag.pubads,typeof googletag.display,googletag.apiReady,
 googletag.pubadsReady,p.getSlots().length,Array.isArray(googletag.sizeMapping().addSize([0,0],[]).build()),
 s.getSlotElementId(),s.getAdUnitPath(),s.getTargeting('k').join(),s.getTargeting('none').length,
 typeof googletag.enums.OutOfPageFormat.INTERSTITIAL,p.refresh()===undefined,googletag.destroySlots([])===true,
 typeof googletag.getVersion(),s.getSlotId().getDomId(),p.definePassback('/1',[1,1]).setTargeting('a','b').display()===undefined];
await __sleep(60);__R.collapsed=document.getElementById('div-gpt-1').style.display;""",
         allowed=["googletag"],
         expect=lambda R: [("q1", R.get("q1") == 1 and R.get("q1this") is True and R.get("q1b") == 1),
                           ("q2-sync", R.get("q2") == 1 and R.get("pushRet") == "number"),
                           ("display", R.get("disp") == 1 and R.get("req") is True),
                           ("slotRenderEnded", R.get("ev") == [True, True, "publisher_ads", None]),
                           ("api", R.get("api") == ["function", "function", "function", True, True, 1, True,
                                                    "div-gpt-1", "/123/x", "a,b", 0, "number", True, True,
                                                    "string", "div-gpt-1", True]),
                           ("collapse", R.get("collapsed") == "none")])
    ads_body = """<ins class="adsbygoogle" id="i1" style="display:inline-block;width:300px;height:250px" data-ad-client="ca-pub-1" data-ad-slot="1"></ins>
<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>
<div style="width:640px"><ins class="adsbygoogle" id="i2" style="display:block" data-ad-format="auto"></ins></div>
<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>"""
    ads_check = """var i1=document.getElementById('i1'),i2=document.getElementById('i2');
var t;try{adsbygoogle.push({});t='ok'}catch(e){t='throw'}
var h=document.getElementById('aswift_0_host');
__R.a=[adsbygoogle.loaded,i1.getAttribute('data-adsbygoogle-status'),i2.getAttribute('data-adsbygoogle-status'),
 !!i1.querySelector('iframe#aswift_0'),!!i2.querySelector('iframe#aswift_1'),h&&h.style.width,h&&h.style.height,
 i1.getAttribute('data-ad-status'),t,adsbygoogle.requestNonPersonalizedAds,Array.isArray(adsbygoogle),
 document.getElementById('aswift_1').getAttribute('width'),document.getElementById('aswift_1').getAttribute('height'),
 document.querySelectorAll('[id^=aswift_]').length];"""
    ads_exp = ["true", "done", "done", True, True, "300px", "250px", None, "ok", 1, False, "640", "280", 4]
    ads_pre = """<script>(adsbygoogle=window.adsbygoogle||[]).push({google_ad_client:'ca-pub-1',enable_page_level_ads:true});
adsbygoogle.requestNonPersonalizedAds=1;</script>"""
    for nm, asy in (("adsbygoogle-sync", False), ("adsbygoogle-async", True)):
        case(nm, "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1",
             pre=ads_pre, body=ads_body, check=ads_check.replace("adsbygoogle.loaded,", "String(adsbygoogle.loaded),"),
             allowed=["adsbygoogle"], is_async=asy,
             expect=lambda R: [("adsense", R.get("a") == ads_exp)])
    case("ima", "https://imasdk.googleapis.com/js/sdkloader/ima3.js",
         check="""var v=document.createElement('video');document.body.appendChild(v);
var c=document.createElement('div');document.body.appendChild(c);
var adc=new google.ima.AdDisplayContainer(c,v);adc.initialize();
var l=new google.ima.AdsLoader(adc);
var p=new Promise(function(res){
 l.addEventListener(google.ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED,function(){__R.aml=1},false);
 l.addEventListener(google.ima.AdErrorEvent.Type.AD_ERROR,function(e){var er=e.getError();
  res([e.type,er.getErrorCode(),er.getVastErrorCode(),er.getType(),er.getMessage(),e.getUserRequestContext().k,
   er instanceof google.ima.AdError,e instanceof google.ima.AdErrorEvent,er.getInnerError()]);},false);});
var rq=new google.ima.AdsRequest();rq.adTagUrl='https://pubads.g.doubleclick.net/gampad/ads?x=1';
rq.linearAdSlotWidth=640;rq.setAdWillAutoPlay(true);rq.setAdWillPlayMuted(true);
l.requestAds(rq,{k:7});
__R.err=await Promise.race([p,__sleep(2000).then(function(){return 'timeout'})]);
var rs=new google.ima.AdsRenderingSettings();rs.restoreCustomPlaybackStateOnAdBreakComplete=true;
google.ima.settings.setLocale('pl');google.ima.settings.setVpaidMode(google.ima.ImaSdkSettings.VpaidMode.ENABLED);
__R.misc=[typeof google.ima.VERSION,google.ima.settings.getLocale(),google.ima.AdEvent.Type.CONTENT_RESUME_REQUESTED,
 google.ima.ViewMode.NORMAL,c.childElementCount,l.getSettings()===google.ima.settings,
 google.ima.AdError.ErrorCode.VAST_EMPTY_RESPONSE,google.ima.UiElements.COUNTDOWN];
var m=new google.ima.AdsManagerLoadedEvent({}).getAdsManager(v,rs);var seq=[];
m.addEventListener(google.ima.AdEvent.Type.CONTENT_RESUME_REQUESTED,function(){seq.push('resume')});
m.addEventListener(google.ima.AdEvent.Type.ALL_ADS_COMPLETED,function(){seq.push('done')});
m.init(640,360,google.ima.ViewMode.NORMAL);m.start();await __sleep(60);
__R.mgr=[seq,m.getCuePoints().length,m.getRemainingTime(),m.getVolume(),m.isCustomPlaybackUsed()];""",
         allowed=["google"],
         expect=lambda R: [("adError", R.get("err") == ["adError", 1009, 303, "adLoadError",
                                                         "The VAST response document is empty.", 7, True, True, None]),
                           ("no-aml", R.get("aml") is None),
                           ("misc", R.get("misc") == ["string", "pl", "contentResumeRequested", "normal", 0, True,
                                                      1009, "countdown"]),
                           ("manager", R.get("mgr") == [["resume", "done"], 0, 0, 1, False])])
    case("analytics", "https://www.google-analytics.com/analytics.js",
         pre="""<script>(function(i,r){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();})(window,'ga');
ga('create','UA-1-1','auto');ga('send','pageview',{hitCallback:function(){__R.hc1=1}});
ga(function(t){__R.ready=t&&t.get('trackingId')});</script>""",
         check="""ga('send','event','c','a',{hitCallback:function(){__R.hc2=1}});
ga('create','UA-2-2','auto','second');ga('second.send','pageview',{hitCallback:function(){__R.hc3=1}});
ga('set','page','/x');ga('require','ec');ga('ec:addProduct',{id:1});
ga('send',{hitType:'pageview',hitCallback:function(){__R.hc4=1}});
await __sleep(60);var t0=ga.getByName('t0');
__R.api=[ga.loaded,ga.getAll().length,t0.get('trackingId'),/^\\d+\\.\\d+$/.test(t0.get('clientId')),
 typeof gaplugins.Linker,t0.get('page'),ga.getByName('nope'),new gaplugins.Linker(t0).decorate('u')];""",
         allowed=["GoogleAnalyticsObject", "ga", "gaplugins"],
         expect=lambda R: [("hitCallbacks", [R.get(k) for k in ("hc1", "hc2", "hc3", "hc4")] == [1, 1, 1, 1]),
                           ("ready", R.get("ready") == "UA-1-1"),
                           ("api", R.get("api") == [True, 2, "UA-1-1", True, "function", "/x", None, "u"])])
    case("ga.js", "https://ssl.google-analytics.com/ga.js",
         pre="""<script>var _gaq=_gaq||[];_gaq.push(['_setAccount','UA-1']);
_gaq.push(['_set','hitCallback',function(){__R.hc=1}]);_gaq.push(['_trackPageview']);</script>""",
         check="""_gaq.push(['_trackEvent','a','b'],function(){__R.fn=1});var t=_gat._getTracker('UA-9');
_gaq.push(['_set','hitCallback',function(){__R.hc2=1}],['_trackEvent','c','d']);
__R.api=[t._getAccount(),_gat._getVersion(),typeof _gaq.push,t._getLinkerUrl('https://x/'),
 _gaq.push(['b._setAccount','UA-3']),_gat._getTrackerByName('b')._getAccount(),t._linkByPost(),
 _gat._getTrackerByName()._getAccount(),t._setCustomVar(1,'a','b',1)];await __sleep(60);""",
         allowed=["_gaq", "_gat"],
         expect=lambda R: [("hitCallback", R.get("hc") == 1 and R.get("hc2") == 1 and R.get("fn") == 1),
                           ("api", R.get("api") == ["UA-9", "5.7.2", "function", "https://x/", 0, "UA-3", True,
                                                    "UA-1", None])])
    gtm_pre = """<script>window.dataLayer=window.dataLayer||[];
dataLayer.push({event:'pre',eventCallback:function(id){__R.pre=id||1},eventTimeout:2000});
function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-1');
gtag('event','pre2',{event_callback:function(){__R.pre2=1}});</script>"""
    gtm_check = """dataLayer.push({event:'post',eventCallback:function(){__R.post=(__R.post||0)+1}});
gtag('event','click',{event_callback:function(){__R.gtagcb=(__R.gtagcb||0)+1}});
gtag('get','G-1','client_id',function(v){__R.get=(v===undefined)});await __sleep(60);
var tm=window.google_tag_manager;
__R.api=[typeof tm,!!(tm&&tm['%s']),tm&&tm['%s']&&tm['%s'].dataLayer.name,Array.isArray(dataLayer),dataLayer.length];"""
    for nm, src, cid in (("gtm", "https://www.googletagmanager.com/gtm.js?id=GTM-ABC12&l=dataLayer", "GTM-ABC12"),
                         ("gtag", "https://www.googletagmanager.com/gtag/js?id=G-XYZ", "G-XYZ")):
        case(nm, src, pre=gtm_pre, check=gtm_check % (cid, cid, cid), allowed=["dataLayer", "gtag", "google_tag_manager"],
             expect=lambda R, cid=cid: [("eventCallback-pre", R.get("pre") == cid and R.get("pre2") == 1),
                                        ("eventCallback-post", R.get("post") == 1 and R.get("gtagcb") == 1),
                                        ("get-cb", R.get("get") is True),
                                        ("api", R.get("api") == ["object", True, "dataLayer", True, 7])])
    case("apstag", "https://c.amazon-adsystem.com/aax2/apstag.js",
         pre="""<script>!function(a9,a){if(a[a9])return;function q(c,r){a[a9]._Q.push([c,r])}a[a9]={init:function(){q("i",arguments)},fetchBids:function(){q("f",arguments)},setDisplayBids:function(){},targetingKeys:function(){return[]},_Q:[]};}("apstag",window);
apstag.init({pubID:'1',adServer:'googletag'},function(){__R.init0=1});
apstag.fetchBids({slots:[{slotID:'d',sizes:[[300,250]]}],timeout:2e3},function(b){__R.fb1=Array.isArray(b)&&b.length===0});</script>""",
         check="""apstag.fetchBids({slots:[]},function(b){__R.fb2=Array.isArray(b)});
apstag._Q.push(['f',[{slots:[]},function(){__R.fb3=1}]]);
apstag.init({},function(){__R.init=1});apstag.setDisplayBids();__R.tk=apstag.targetingKeys();await __sleep(60);""",
         allowed=["apstag"],
         expect=lambda R: [("fetchBids", R.get("fb1") is True and R.get("fb2") is True and R.get("fb3") == 1),
                           ("init", R.get("init0") == 1 and R.get("init") == 1 and R.get("tk") == [])])
    case("ad_status", "https://static.doubleclick.net/instream/ad_status.js",
         check="__R.s=window.google_ad_status;", allowed=["google_ad_status"],
         expect=lambda R: [("status", R.get("s") == 1)])
    case("nofab", "https://site.test/js/fuckadblock.js",
         check="""__R.t=[typeof FuckAdBlock,typeof fuckAdBlock,typeof BlockAdBlock,typeof blockAdBlock,typeof sniffAdBlock,typeof SniffAdBlock];
fuckAdBlock.onDetected(function(){__R.det=1});fuckAdBlock.onNotDetected(function(){__R.nd=1});
var f=new FuckAdBlock({checkOnLoad:false});f.setOption('debug',true).on(true,function(){__R.det2=1}).on(false,function(){__R.nd2=1});
window.fuckAdBlock=123;__R.ro=typeof fuckAdBlock;__R.chk=blockAdBlock.check();blockAdBlock.emitEvent(true);await __sleep(60);""",
         allowed=["FuckAdBlock", "BlockAdBlock", "SniffAdBlock", "fuckAdBlock", "blockAdBlock", "sniffAdBlock"],
         expect=lambda R: [("types", R.get("t") == ["function", "object", "function", "object", "object", "function"]),
                           ("notDetected", R.get("nd") == 1 and R.get("nd2") == 1 and R.get("chk") is True),
                           ("neverDetected", R.get("det") is None and R.get("det2") is None),
                           ("readonly", R.get("ro") == "object")])
    case("nobab", "https://res.test/nobab.js", csp=CSP_EVAL,
         check="""document.body.style.visibility='hidden';
__R.e1=eval('1+1');__R.e2=eval("var a='ABCD'; var babasbmsgx=1; /* blockadblock */ document.body.style.visibility='hidden'; 5");
__R.vis=document.body.style.visibility;var d=document.createElement('div');d.id='babasbmsgx';document.body.appendChild(d);
__R.st=setTimeout("foo.bab_elementidX",10);__R.st2=typeof setTimeout(function(){},1);await __sleep(700);
__R.gone=!document.getElementById('babasbmsgx');""",
         expect=lambda R: [("eval-normal", R.get("e1") == 2), ("eval-bab", R.get("e2") is None),
                           ("undo", R.get("vis") == "" and R.get("gone") is True),
                           ("timer", R.get("st") == 0 and R.get("st2") == "number")])
    case("noeval", "https://res.test/silent-noeval.js", csp=CSP_EVAL,
         check="__R.e=eval('1+1');__R.t=typeof eval;",
         expect=lambda R: [("noeval", R.get("e") is None and R.get("t") == "function")])
    case("popads", "https://res.test/popads.net.js",
         check="try{window.PopAds={};__R.w='ok'}catch(e){__R.w=e.name}__R.g=typeof PopAds;",
         allowed=["PopAds", "popns"], expect=lambda R: [("abort", R.get("w") == "ReferenceError" and R.get("g") == "undefined")])
    case("popads-dummy", "https://res.test/set-popads-dummy",
         check="window.PopAds=5;__R.g=[typeof PopAds,typeof popns];",
         allowed=["PopAds", "popns"], expect=lambda R: [("dummy", R.get("g") == ["object", "object"])])
    case("prebid-ads", "https://site.test/ads/prebid-ads.js",
         check="__R.v=[window.canRunAds,window.isAdBlockActive];", allowed=["canRunAds", "isAdBlockActive"],
         expect=lambda R: [("flags", R.get("v") == [True, False])])
    case("fingerprint2", "https://res.test/fingerprintjs2",
         check="""new Fingerprint2().get(function(h,c){__R.h=[h.length,Array.isArray(c)]});
Fingerprint2.get({},function(c){__R.g=Array.isArray(c)});Fingerprint2.getV18(function(h){__R.v18=h.length});
__R.p=Array.isArray(await Fingerprint2.getPromise());var x=Fingerprint2.x64hash128('abc',31);
__R.x=[x.length,/^[0-9a-f]{32}$/.test(x),x===Fingerprint2.x64hash128('abc',31),x!==Fingerprint2.x64hash128('abd',31),Fingerprint2.VERSION];await __sleep(60);""",
         allowed=["Fingerprint2"],
         expect=lambda R: [("cb", R.get("h") == [32, True] and R.get("g") is True and R.get("v18") == 32 and R.get("p") is True),
                           ("hash", R.get("x") == [32, True, True, True, "2.1.4"])])
    case("fingerprint3", "https://res.test/fingerprint3.js",
         check="var a=await FingerprintJS.load();var r=await a.get();__R.v=[r.visitorId.length,r.confidence.score,r.version];",
         allowed=["FingerprintJS"], expect=lambda R: [("agent", R.get("v") == [32, 0.5, "3.4.2"])])
    case("ampproject", "https://cdn.ampproject.org/v0.js",
         pre="""<style amp-boilerplate>body{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}@keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}</style><noscript><style amp-boilerplate>body{animation:none}</style></noscript>""",
         body="<p>tekst</p>",
         check="__R.v=[getComputedStyle(document.body).visibility,document.querySelectorAll('style[amp-boilerplate]').length,document.querySelectorAll('noscript').length];",
         expect=lambda R: [("visible", R.get("v") == ["visible", 0, 0])])
    case("scorecard", "https://sb.scorecardresearch.com/beacon.js",
         pre="<script>var _comscore=_comscore||[];_comscore.push({c1:'2',c2:'1'});</script>",
         check="__R.v=[typeof COMSCORE.beacon,_comscore.length];COMSCORE.purge();__R.p=Array.isArray(_comscore);",
         allowed=["_comscore", "COMSCORE"], expect=lambda R: [("api", R.get("v") == ["function", 0] and R.get("p") is True)])
    case("outbrain", "https://widgets.outbrain.com/outbrain.js",
         check="OBR.extern.callRecs({},function(r){__R.cb=typeof r});OBR.extern.refreshWidget();__R.v=typeof OBR.extern.video.getVideoRecs;await __sleep(30);",
         allowed=["OBR"], expect=lambda R: [("api", R.get("cb") == "object" and R.get("v") == "function")])
    case("cx_api", "https://res.test/google-analytics.com/cx/api.js",
         check="__R.v=[cxApi.chooseVariation(),cxApi.NOT_PARTICIPATING];", allowed=["cxApi"],
         expect=lambda R: [("api", R.get("v") == [0, -2])])
    case("inpage_linkid", "https://res.test/google-analytics.com/inpage_linkid.js",
         check="__R.v=Array.isArray(window._gaq);", allowed=["_gaq"], expect=lambda R: [("gaq", R.get("v") is True)])
    case("amazon_ads", "https://c.amazon-adsystem.com/aax2/amzn_ads.js",
         check="amznads.getAdsCallback('x',function(){__R.cb=1});__R.v=[amznads.appendTargetingToQueryString('q'),typeof aax_write];await __sleep(30);",
         allowed=["amznads", "amzn_ads", "aax_getad_mpb", "aax_write", "aax_render_ad"],
         expect=lambda R: [("api", R.get("cb") == 1 and R.get("v") == ["q", "function"])])
    case("sensors", "https://static.example.cn/lib/sensorsdata.full.min.js",
         pre="""<script>window.sensorsDataAnalytic201505='sensors';window.sensors=function(){};
sensors._q=[['track',['ev',{},function(){__R.q=1}]]];</script>""",
         check="sensors.track('e',{a:1},function(){__R.cb=1});__R.v=[sensors===sensorsDataAnalytic201505,typeof sensors.getDistinctId()];await __sleep(30);",
         allowed=["sensors", "sensorsDataAnalytic201505"],
         expect=lambda R: [("api", R.get("q") == 1 and R.get("cb") == 1 and R.get("v") == [True, "string"])])
    case("nitropay", "https://res.test/nitropay_ads.js",
         pre="""<script>window.nitroAds={createAd:function(){var a=arguments;return new Promise(function(r){nitroAds.queue.push(['createAd',a,r])})},queue:[]};
nitroAds.createAd('x',{}).then(function(a){__R.q=a.id});</script>""",
         check="var a=await nitroAds.createAd('y',{});__R.v=[nitroAds.loaded,a.id,typeof a.remove];await __sleep(10);",
         allowed=["nitroAds"], expect=lambda R: [("api", R.get("q") == "x" and R.get("v") == [True, "y", "function"])])
    case("chartbeat", "https://static.chartbeat.com/chartbeat.js",
         check="__R.v=typeof pSUPERFLY.virtualPage;", allowed=["pSUPERFLY"],
         expect=lambda R: [("api", R.get("v") == "function")])
    case("default-noop.js", "https://ads.ad/some/lib.js", check="", expect=lambda R: [])
    # media / obrazy / ramki / css / fetch – wszystko przez przekierowanie
    case("media", "", csp="script-src 'unsafe-inline' https:", visible=True,
         body="""<img id="m1" src="https://ads.ad/banner.jpg"><img id="m2" src="https://res.test/1x1-transparent.gif">
<img id="m3" src="https://res.test/3x2.png"><img id="m4" src="https://ads.ad/favicon.ico"><img id="m5" src="https://res.test/32x32-transparent-png">
<iframe id="f1" src="https://ads.ad/frame.html" onload="__R.f1=1"></iframe>
<iframe id="f2" src="https://res.test/click2load.html?url=https%3A%2F%2Fwww.youtube.com%2Fembed%2Fx" onload="__R.f2=1"></iframe>
<link rel="stylesheet" href="https://ads.ad/a.css" onload="__R.css=1" onerror="__R.css=-1">""",
         check="""var im=function(id){var e=document.getElementById(id);return [e.complete,e.naturalWidth,e.naturalHeight]};
__R.img=[im('m1'),im('m2'),im('m3'),im('m4'),im('m5')];
var play=function(src,tag){return new Promise(function(res){var e=document.createElement(tag);e.muted=true;
 var t=setTimeout(function(){res('timeout:'+(e.error&&e.error.code))},6000);
 e.onended=function(){clearTimeout(t);res(['ended',Math.round(e.duration*10)/10])};
 e.onerror=function(){clearTimeout(t);res('error:'+(e.error&&e.error.code))};
 e.src=src;document.body.appendChild(e);var p=e.play();if(p&&p.catch)p.catch(function(x){res('play:'+x.name+':'+x.message)});});};
__R.media=await Promise.all([play('https://ads.ad/a.mp3','audio'),play('https://ads.ad/v.mp4','video'),
 play('https://res.test/noopmp4-1s','video'),play('https://res.test/noop-1s.webm','video'),play('https://res.test/noop-0.5s.mp3','audio')]);
var f=await fetch('https://ads.ad/ping.txt',{mode:'no-cors'});__R.fetch=[f.status,(await f.text()).length];
var x=await fetch('https://res.test/noopvast-3.0',{mode:'no-cors'});__R.vast=(await x.text()).indexOf('<VAST version="3.0">')>=0;""",
         expect=lambda R: [("images", R.get("img") == [[True, 2, 2], [True, 1, 1], [True, 3, 2], [True, 32, 32], [True, 32, 32]]),
                           ("frames", R.get("f1") == 1 and R.get("f2") == 1),
                           ("css", R.get("css") == 1),
                           ("media", isinstance(R.get("media"), list) and all(isinstance(m, list) and m[0] == "ended" for m in R["media"])),
                           ("fetch", R.get("fetch") == [200, 0] and R.get("vast") is True)])


def all_js_cases():
    for n, (mime, _src) in res._TABLE.items():
        if mime == "application/javascript":
            case("load:" + n, "https://res.test/" + n, check="", allowed=["*"], expect=lambda R: [])


def qt_tests():
    tmp = tempfile.mkdtemp(prefix="luna_res_test_")
    for k in ("USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA"):
        os.environ[k] = tmp

    def boom():
        print("WATCHDOG: hard exit", flush=True)
        os._exit(3)
    wd = threading.Timer(240, boom)
    wd.daemon = True
    wd.start()

    from PyQt6.QtCore import QBuffer, QByteArray, QEventLoop, QIODevice, QTimer, QUrl
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
                                       QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor,
                                       QWebEngineUrlRequestJob, QWebEngineUrlScheme, QWebEngineUrlSchemeHandler)

    scheme = "x" + secrets.token_hex(5)
    token = secrets.token_urlsafe(12)
    SR = f"{scheme}://l/{token}/"
    sch = QWebEngineUrlScheme(scheme.encode())
    sch.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    F = QWebEngineUrlScheme.Flag
    sch.setFlags(F.SecureScheme | F.ContentSecurityPolicyIgnored | F.CorsEnabled | F.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(sch)
    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu",
                        "--autoplay-policy=no-user-gesture-required", "--disable-background-media-suspend","--host-resolver-rules=MAP * ~NOTFOUND"])

    RTM = QWebEngineUrlRequestInfo.ResourceType
    rt_map = {RTM.ResourceTypeScript: 4, RTM.ResourceTypeImage: 5, RTM.ResourceTypeStylesheet: 3,
              RTM.ResourceTypeSubFrame: 2, RTM.ResourceTypeMedia: 8, RTM.ResourceTypeXhr: 9,
              RTM.ResourceTypeFontResource: 6, RTM.ResourceTypeFavicon: 5}
    served = []
    redirected = []
    errors = []

    class Handler(QWebEngineUrlSchemeHandler):
        def requestStarted(self, job):
            try:
                u = job.requestUrl()
                parts = u.path().split("/", 3)
                if u.host() == "l" and len(parts) == 4 and parts[1] == token and parts[2] == "r":
                    r = res.get(QUrl.fromPercentEncoding(parts[3].encode()))
                    if r:
                        buf = QBuffer(job)
                        buf.setData(QByteArray(r[1]))
                        buf.open(QIODevice.OpenModeFlag.ReadOnly)
                        served.append(parts[3])
                        job.reply(r[0].encode(), buf)
                        return
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            except Exception as e:
                errors.append(repr(e))

    class Interceptor(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            try:
                u = info.requestUrl()
                if u.scheme() == scheme or u.scheme() not in ("http", "https"):
                    return
                host = u.host().lower()
                url = bytes(u.toEncoded()).decode()
                rt = rt_map.get(info.resourceType(), 12)
                name = None
                if host == "res.test":
                    name = u.path()[1:]
                    if u.hasQuery():
                        name += "?" + u.query()
                else:
                    name = res.known_library(url, rt)
                    if name is None and host.endswith(".ad"):
                        name = res.default_for(rt, url)
                if name:
                    base, _, q = name.partition("?")
                    if res.get(base) is None:
                        info.block(True)
                        return
                    redirected.append((url, base))
                    info.redirect(QUrl(SR + "r/" + base + ("?" + q if q else "")))
                elif host != "site.test":
                    info.block(True)
            except Exception as e:
                errors.append(repr(e))

    profile = QWebEngineProfile()  # off-the-record
    handler = Handler(profile)
    interceptor = Interceptor(profile)
    profile.installUrlSchemeHandler(scheme.encode(), handler)
    profile.setUrlRequestInterceptor(interceptor)
    profile.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)

    class Page(QWebEnginePage):
        def __init__(self, prof):
            super().__init__(prof)
            self.console = []

        def javaScriptConsoleMessage(self, level, msg, line, src):
            self.console.append((getattr(level, "name", str(level)), msg[:300]))

    def pump(ms):
        loop = QEventLoop()
        QTimer.singleShot(int(ms), loop.quit)
        loop.exec()

    def run_js(page, code, timeout=5.0):
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

    t_all = time.perf_counter()
    for name, src, kw, expect in CASES:
        page = Page(profile)
        allowed = kw.get("allowed", ())
        html = page_html(src, kw.get("pre", ""), kw.get("body", ""), kw.get("check", ""),
                         [] if "*" in allowed else allowed, kw.get("csp", CSP_STRICT), kw.get("is_async", False))
        n_red = len(redirected)
        view = None
        if kw.get("visible"):
            # media w niewidocznej stronie Chromium wstrzymuje ("background media paused") -> mały widok
            view = QWebEngineView()
            view.setPage(page)
            view.resize(320, 240)
            view.show()
        page.setHtml(html, QUrl("https://site.test/"))
        end = time.perf_counter() + 15
        out = None
        while time.perf_counter() < end:
            pump(40)
            v = run_js(page, "window.__done||null")
            if v:
                out = json.loads(v)
                break
        if out is None:
            check(name + ":done", False, "timeout")
            page.deleteLater()
            continue
        if src:
            check(name + ":load", out.get("load") == 1, out.get("load"))
            if not src.startswith("https://site.test/") or "fuckadblock" in src or "prebid" in src:
                check(name + ":redirected", len(redirected) > n_red, redirected[n_red:])
        check(name + ":no-exception", "exc" not in out, out.get("exc"))
        check(name + ":no-errors", not out.get("errs"), out.get("errs"))
        if "*" not in allowed:
            check(name + ":no-leaked-globals", not out.get("leak"), out.get("leak"))
        check(name + ":no-console", not page.console, page.console)
        for sub, ok in expect(out):
            check(name + ":" + sub, ok, json.dumps(out)[:600])
        if view is not None:
            view.hide()
            view.deleteLater()
        page.deleteLater()
        pump(5)
    check("qt:no-python-errors", not errors, errors)
    check("qt:resources-served", len(served) >= len(CASES), len(served))
    print(f"Qt: {len(CASES)} pages, {len(redirected)} redirects, {len(served)} scheme replies, "
          f"{time.perf_counter() - t_all:.1f}s", flush=True)
    wd.cancel()


def main():
    unit_tests()
    if "--no-qt" not in sys.argv:
        define_cases()
        all_js_cases()
        only = [a[7:] for a in sys.argv if a.startswith("--only=")]
        if only:
            CASES[:] = [c for c in CASES if any(o in c[0] for o in only)]
        qt_tests()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed", flush=True)
    sys.stdout.flush()
    os._exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
