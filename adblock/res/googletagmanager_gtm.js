(function () {
    'use strict';
    var w = window;
    var src = '';
    try { src = document.currentScript && document.currentScript.src || ''; } catch (e) {}
    var qs = function (k) {
        var m = new RegExp('[?&]' + k + '=([^&#]*)').exec(src);
        if (!m) { return ''; }
        try { return decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { return m[1]; }
    };
    var id = qs('id');
    var l = qs('l') || 'dataLayer';
    if (!/^[A-Za-z_$][\w$]*$/.test(l)) { l = 'dataLayer'; }
    var noop = function () {};
    var tm = w.google_tag_manager;
    if (tm === null || typeof tm !== 'object') { tm = w.google_tag_manager = {}; }
    if (id && !tm[id]) {
        tm[id] = {
            dataLayer: { name: l, get: noop, set: noop, reset: noop },
            callback: noop,
            onHtmlSuccess: function () { return noop; },
            onHtmlFailure: function () { return noop; }
        };
    }
    var call = function (fn) {
        if (typeof fn !== 'function') { return; }
        setTimeout(function () { try { fn(id || undefined); } catch (e) {} }, 0);
    };
    var isArgs = function (e) { return Object.prototype.toString.call(e) === '[object Arguments]'; };
    var handle = function (e) {
        if (!e || typeof e !== 'object') { return; }
        if (isArgs(e) || Array.isArray(e)) {
            var kind = e[0];
            if (kind === 'event') {
                var p = e[2];
                if (p && typeof p === 'object') { call(p.event_callback, p.event_timeout); }
            } else if (kind === 'get') {
                var cb = e[3];
                if (typeof cb === 'function') {
                    setTimeout(function () { try { cb(undefined); } catch (x) {} }, 0);
                }
            }
            return;
        }
        if (typeof e.eventCallback === 'function') { call(e.eventCallback, e.eventTimeout); }
    };
    var dl = w[l];
    if (!Array.isArray(dl)) { dl = w[l] = []; }
    var push = Array.prototype.push;
    var wrapped = function () {
        var r = push.apply(dl, arguments);
        for (var i = 0; i < arguments.length; i++) {
            try { handle(arguments[i]); } catch (x) {}
        }
        return r;
    };
    var cur = dl.push;
    if (typeof cur !== 'function' || Function.prototype.toString.call(cur) !== Function.prototype.toString.call(wrapped)) {
        Object.defineProperty(dl, 'push', { value: wrapped, writable: true, configurable: true, enumerable: false });
        for (var i = 0; i < dl.length; i++) {
            try { handle(dl[i]); } catch (x) {}
        }
    }
})();
