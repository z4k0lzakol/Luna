(function () {
    'use strict';
    var w = window;
    var noop = function () {};
    var o = w.OBR;
    if (o === null || typeof o !== 'object') { o = {}; }
    var ext = {};
    ['callClick', 'callWhatIs', 'closeCard', 'closeModal', 'getCountOfRecs', 'getStat', 'imageError',
        'manualVideoClicked', 'onOdbReturn', 'onVideoRecsReturn', 'refreshSpecificWidget', 'refreshWidget',
        'reloadWidget', 'researchWidget', 'returnedError', 'returnedHtmlData', 'returnedIrdData',
        'returnedJsonData', 'scrollLoad', 'showDescription', 'showRecInIframe', 'userClosedWindow',
        'videoRecsInfo'].forEach(function (n) { ext[n] = noop; });
    ext.callRecs = function (json, cb) {
        if (typeof cb === 'function') { setTimeout(function () { try { cb({}); } catch (e) {} }, 0); }
    };
    ext.video = { getVideoRecs: noop, videoClicked: noop };
    o.extern = ext;
    w.OBR = o;
})();
