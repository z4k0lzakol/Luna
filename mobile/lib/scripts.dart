// Skrypty uruchamiane na stronach (własny kod Luny).

/// YouTube bez reklam: z odpowiedzi odtwarzacza usuwamy dane o reklamach, zanim odtwarzacz je odczyta,
/// chowamy reklamy w kanale, a gdy reklama mimo to się pojawi – przewijamy ją i klikamy „Pomiń”.
const youtubeScript = r'''
(function () {
  if (!/(^|\.)youtube\.com$/.test(location.hostname) || window.__lunaYt) return;
  window.__lunaYt = true;
  var KEYS = ['adPlacements', 'playerAds', 'adSlots', 'adBreakHeartbeatParams'];
  function strip(o, depth) {
    if (!o || typeof o !== 'object' || depth > 5) return o;
    if (Array.isArray(o)) { for (var i = 0; i < o.length; i++) strip(o[i], depth + 1); return o; }
    for (var k = 0; k < KEYS.length; k++) if (KEYS[k] in o) delete o[KEYS[k]];
    if (o.playerResponse) strip(o.playerResponse, depth + 1);
    if (o.response) strip(o.response, depth + 1);
    return o;
  }
  var parse = JSON.parse;
  JSON.parse = function () { var r = parse.apply(this, arguments); try { strip(r, 0); } catch (e) {} return r; };
  var rj = Response.prototype.json;
  Response.prototype.json = function () {
    return rj.apply(this, arguments).then(function (r) { try { strip(r, 0); } catch (e) {} return r; });
  };
  var ip;
  try {
    Object.defineProperty(window, 'ytInitialPlayerResponse', {
      configurable: true, get: function () { return ip; }, set: function (v) { ip = strip(v, 0); }
    });
  } catch (e) {}
  var css = 'ytm-promoted-sparkles-web-renderer,ytm-companion-ad-renderer,ad-slot-renderer,ytd-ad-slot-renderer,' +
    'ytm-promoted-video-renderer,ytd-in-feed-ad-layout-renderer,ytm-ad-slot-renderer,.ytp-ad-module,#player-ads,' +
    'ytd-promoted-sparkles-web-renderer,ytm-rich-item-renderer:has(ad-slot-renderer){display:none!important}';
  function addCss() {
    var root = document.head || document.documentElement;
    if (!root) return setTimeout(addCss, 50);
    var s = document.createElement('style'); s.textContent = css; root.appendChild(s);
  }
  addCss();
  setInterval(function () {
    var v = document.querySelector('.ad-showing video');
    if (v && isFinite(v.duration) && v.duration > 0) { v.muted = true; v.currentTime = v.duration; }
    var b = document.querySelector('.ytp-ad-skip-button,.ytp-ad-skip-button-modern,.ytp-skip-ad-button');
    if (b) b.click();
  }, 400);
})();
''';

/// Tryb czytania: tytuł i akapity głównej treści strony (JSON).
const readerScript = r'''
(function () {
  function score(el) { var t = el.innerText || ''; return t.length + el.querySelectorAll('p').length * 120; }
  var BAD = /comment|share|social|related|promo|advert|sponsor|sidebar|newsletter|subscribe|cookie|footer|nav|menu|banner|popup/i;
  var best = document.querySelector('article') || null, bestScore = best ? score(best) : 0;
  document.querySelectorAll('main, article, section, div').forEach(function (el) {
    if (BAD.test((el.id || '') + ' ' + (el.className || ''))) return;
    var ps = el.querySelectorAll(':scope > p').length;
    if (ps < 2) return;
    var s = score(el);
    if (s > bestScore) { best = el; bestScore = s; }
  });
  var root = best || document.body, out = [];
  root.querySelectorAll('h2, h3, p, li, blockquote').forEach(function (el) {
    if (el.closest('nav, footer, aside, form')) return;
    var t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (t.length < (el.tagName === 'P' ? 25 : 3)) return;
    out.push({ h: /^H/.test(el.tagName), t: t });
  });
  var h1 = document.querySelector('h1');
  return JSON.stringify({ title: (h1 && h1.innerText.trim()) || document.title, site: location.hostname, items: out.slice(0, 400) });
})();
''';

/// Ciemny tryb dowolnej strony (odwrócenie barw z zachowaniem zdjęć i filmów).
String darkScript(bool on) => '''
(function () {
  var id = '__luna_dark', s = document.getElementById(id);
  if (!$on) { if (s) s.remove(); return; }
  if (s) return;
  s = document.createElement('style'); s.id = id;
  s.textContent = 'html{filter:invert(1) hue-rotate(180deg)!important;background:#fff!important}' +
    'img,video,picture,canvas,iframe,svg image,[style*="background-image"]{filter:invert(1) hue-rotate(180deg)!important}';
  (document.head || document.documentElement).appendChild(s);
})();
''';

/// Zaznaczony tekst (do asystenta AI).
const selectionScript = "(window.getSelection && window.getSelection().toString()) || ''";
