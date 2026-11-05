(function () {
    'use strict';
    var w = window;
    var noop = function () {};
    var a = w.amznads;
    if (a === null || typeof a !== 'object') { a = {}; }
    ['getAds', 'setTargeting', 'setTargetingForGPTAsync', 'setTargetingForGPTSync', 'tryGetAdsAsync',
        'updateAds', 'renderAd', 'doAllTasks', 'appendScriptTag'].forEach(function (n) { a[n] = noop; });
    a.getAdsCallback = function (id, cb) {
        if (typeof cb === 'function') { setTimeout(function () { try { cb(); } catch (e) {} }, 0); }
    };
    a.appendTargetingToAdServerUrl = function (u) { return u; };
    a.appendTargetingToQueryString = function (q) { return q; };
    a.getKeys = function () { return []; };
    a.getTargeting = function () { return {}; };
    w.amznads = a;
    w.amzn_ads = w.amzn_ads || noop;
    w.aax_getad_mpb = w.aax_getad_mpb || noop;
    w.aax_write = w.aax_write || noop;
    w.aax_render_ad = w.aax_render_ad || noop;
})();
