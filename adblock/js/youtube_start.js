// Luna – szybszy start filmów na YouTube przy włączonej blokadzie reklam.
//
// Gdy YouTube przygotował dla filmu reklamę, a blokada ją usunęła, serwer odtwarzania każe odtwarzaczowi
// odczekać mniej więcej długość reklamy (5–11 s) – odtwarzacz „kręci kółkiem”, nic nie pobierając.
// Ten skrypt rozpoznaje taki stan (serwer już odpowiedział, a bufor dalej pusty, obraz 0x0, brak reklamy na
// ekranie) i od razu wczytuje film ponownie w trybie bez reklam – ten sam znacznik klienta, którego używają
// reguły list uBlock („; oaeb” w userAgent kontekstu InnerTube; reguła trusted-edit-inbound-object dopisuje
// wtedy do zapytania o film parametry bez reklam). Z czterech wariantów z list ten startuje najszybciej
// (pomiar w Lunie: ok. 5 s zamiast 11 s). Każdy film jest przeładowywany najwyżej raz.
(function () {
  if (window.__lunaYtStart) return;
  window.__lunaYtStart = true;
  var MARK = 'oaeb', MIN = 700, IDLE = 500, WAIT = 2300, GIVE_UP = 15000;
  var lastId = null, t0 = 0, done = false;

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  function setMark() {
    try {
      var c = window.ytcfg && ytcfg.data_ && ytcfg.data_.INNERTUBE_CONTEXT && ytcfg.data_.INNERTUBE_CONTEXT.client;
      if (!c || typeof c.userAgent !== 'string' || /; (adunit|channel|inline|yahi|oaeb|eafg|yaf4)\b/.test(c.userAgent)) return;
      var m = c.userAgent.match(/Mozilla\/5\.0 \([^)]+/);
      if (m) c.userAgent = c.userAgent.replace(m[0], m[0] + '; ' + MARK);
    } catch (e) {}
  }

  // czy serwer odpowiedział na zapytanie o obraz/dźwięk tego filmu co najmniej IDLE ms temu
  function answered() {
    try {
      var es = performance.getEntriesByType('resource'), t = now();
      for (var i = es.length - 1; i >= 0; i--) {
        var e = es[i];
        if (e.startTime < t0) break;
        if (e.name.indexOf('.googlevideo.com/videoplayback') > 0 && e.responseEnd > 0 && t - e.responseEnd > IDLE) return true;
      }
    } catch (e) {}
    return false;
  }

  function stuck(p) {
    var v = document.querySelector('video.html5-main-video');
    if (!v || v.readyState !== 0) return false;
    if (p.getPlayerState() !== 3) return false;                   // 3 = buforowanie (nie: pauza / brak autoodtwarzania)
    if (p.classList && p.classList.contains('ad-showing')) return false;
    try {
      var s = p.getStatsForNerds && p.getStatsForNerds();
      if (s && s.resolution && s.resolution.indexOf('0x0') !== 0) return false;
      if (s && s.debug_info && s.debug_info.indexOf('SSAP, AD') === 0) return false;
    } catch (e) {}
    return true;
  }

  function tick() {
    if (location.pathname !== '/watch') return;
    var p = document.getElementById('movie_player');
    if (!p || !p.getVideoData || !p.getPlayerState) return;
    var id = null;
    try { id = p.getVideoData().video_id; } catch (e) {}
    if (!id) return;
    if (id !== lastId) { lastId = id; t0 = now(); done = false; return; }
    if (done) return;
    var dt = now() - t0;
    if (dt > GIVE_UP) { done = true; return; }
    if (dt < MIN || !(dt >= WAIT || answered()) || !stuck(p)) return;
    done = true;
    var start = 0;
    try {
      var r = p.getPlayerResponse && p.getPlayerResponse();
      start = (r && r.playerConfig && r.playerConfig.playbackStartConfig && r.playerConfig.playbackStartConfig.startSeconds) ||
              parseInt(new URLSearchParams(location.search).get('t'), 10) || 0;
    } catch (e) {}
    setMark();
    try { p.loadVideoById(id, start); } catch (e) {}
  }

  setInterval(tick, 250);
})();
