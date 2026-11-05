(function () {
    'use strict';
    var w = window;
    var hex = function (n) {
        var s = '';
        for (var i = 0; i < n; i++) { s += Math.floor(Math.random() * 16).toString(16); }
        return s;
    };
    var hash = hex(32);
    var components = [
        { key: 'userAgent', value: navigator.userAgent },
        { key: 'language', value: navigator.language },
        { key: 'timezoneOffset', value: new Date().getTimezoneOffset() }
    ];
    var later = function (fn, a, b) {
        if (typeof fn !== 'function') { return; }
        setTimeout(function () { try { fn(a, b); } catch (e) {} }, 1);
    };
    var cbOf = function (a, b) { return typeof a === 'function' ? a : b; };
    var Fingerprint2 = function (options) { this.options = options || {}; };
    Fingerprint2.prototype.get = function (cb) { later(cb, hash, components); };
    Fingerprint2.get = function (a, b) { later(cbOf(a, b), components); };
    Fingerprint2.getPromise = function () { return Promise.resolve(components); };
    Fingerprint2.getV18 = function (a, b) { later(cbOf(a, b), hash, components); };
    Fingerprint2.x64hash128 = function (key, seed) {
        var s = String(key);
        var h = [(seed | 0) ^ 0x6a09e667, 0xbb67ae85 ^ (seed | 0), 0x3c6ef372, 0xa54ff53a];
        for (var i = 0; i < s.length; i++) {
            var c = s.charCodeAt(i);
            for (var j = 0; j < 4; j++) {
                h[j] = Math.imul(h[j] ^ (c + j * 131), 0x9e3779b1 + j * 2) >>> 0;
                h[j] = (h[j] << 13 | h[j] >>> 19) >>> 0;
            }
        }
        var out = '';
        for (var k = 0; k < 4; k++) {
            var x = Math.imul(h[k] ^ h[(k + 1) % 4] >>> 15, 0x85ebca6b) >>> 0;
            out += ('00000000' + x.toString(16)).slice(-8);
        }
        return out;
    };
    Fingerprint2.VERSION = '2.1.4';
    Fingerprint2.NOT_AVAILABLE = 'not available';
    Fingerprint2.ERROR = 'error';
    Fingerprint2.EXCLUDED = 'excluded';
    w.Fingerprint2 = Fingerprint2;
})();
