(function () {
    'use strict';
    var w = window;
    var d = document;
    var old = w.adsbygoogle;
    if (old && old.loaded === true && typeof old.push === 'function' && !Array.isArray(old)) { return; }
    var n = 0;
    while (d.getElementById('aswift_' + n)) { n++; }
    var px = function (v) {
        var m = /^(\d+(?:\.\d+)?)px$/.exec(String(v || '').trim());
        return m ? Math.round(parseFloat(m[1])) : 0;
    };
    var fill = function (ins) {
        if (!ins || ins.nodeType !== 1 || ins.getAttribute('data-adsbygoogle-status')) { return; }
        ins.setAttribute('data-adsbygoogle-status', 'done');
        var W = px(ins.style.width);
        var H = px(ins.style.height);
        if (!W) {
            var p = ins.parentElement;
            W = Math.round((p && p.clientWidth) || ins.clientWidth || 300);
        }
        if (!H) { H = 280; }
        var id = 'aswift_' + n++;
        var host = d.createElement('div');
        host.id = id + '_host';
        host.setAttribute('style', 'border:none;height:' + H + 'px;width:' + W + 'px;margin:0;padding:0;position:relative;visibility:visible;background-color:transparent;display:inline-block;overflow:hidden;opacity:0');
        var f = d.createElement('iframe');
        f.id = id;
        f.name = id;
        f.setAttribute('width', String(W));
        f.setAttribute('height', String(H));
        f.setAttribute('frameborder', '0');
        f.setAttribute('marginwidth', '0');
        f.setAttribute('marginheight', '0');
        f.setAttribute('vspace', '0');
        f.setAttribute('hspace', '0');
        f.setAttribute('allowtransparency', 'true');
        f.setAttribute('scrolling', 'no');
        f.setAttribute('style', 'left:0;position:absolute;top:0;border:0;width:' + W + 'px;height:' + H + 'px');
        host.appendChild(f);
        ins.appendChild(host);
    };
    var isConfig = function (o) {
        if (!o || typeof o !== 'object') { return false; }
        return 'google_ad_client' in o || 'enable_page_level_ads' in o || 'overlays' in o ||
            'params' in o || 'google_adtest' in o || 'google_reactive_ad_format' in o;
    };
    var handle = function (item) {
        if (item && typeof item === 'object' && item.element) { fill(item.element); return; }
        if (isConfig(item)) { return; }
        var list = d.querySelectorAll('ins.adsbygoogle');
        for (var i = 0; i < list.length; i++) {
            if (!list[i].getAttribute('data-adsbygoogle-status')) { fill(list[i]); return; }
        }
    };
    var q = {
        loaded: true,
        push: function (item) {
            try { handle(item); } catch (e) {}
        }
    };
    if (old && typeof old === 'object') {
        ['requestNonPersonalizedAds', 'pauseAdRequests', 'google_ad_client'].forEach(function (k) {
            if (k in old) { q[k] = old[k]; }
        });
    }
    w.adsbygoogle = q;
    if (Array.isArray(old)) {
        for (var i = 0; i < old.length; i++) { q.push(old[i]); }
    }
})();
