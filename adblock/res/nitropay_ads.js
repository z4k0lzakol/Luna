(function () {
    'use strict';
    var w = window;
    var noop = function () {};
    var n = w.nitroAds;
    if (n === null || typeof n !== 'object') { n = {}; }
    var stub = function (id) {
        return { id: id, onNavigate: noop, remove: noop, renderAd: noop, refresh: noop };
    };
    var old = Array.isArray(n.queue) ? n.queue : [];
    n.loaded = true;
    n.createAd = function (id) { return Promise.resolve(stub(id)); };
    n.addUserToken = noop;
    n.queue = [];
    w.nitroAds = n;
    for (var i = 0; i < old.length; i++) {
        var e = old[i];
        if (!e) { continue; }
        try {
            if (e[0] === 'createAd') {
                var a = e[1] || [];
                if (typeof e[2] === 'function') { e[2](stub(a[0])); }
            }
        } catch (x) {}
    }
})();
