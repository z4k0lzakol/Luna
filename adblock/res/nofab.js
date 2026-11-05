(function () {
    'use strict';
    var w = window;
    var later = function (fn) {
        if (typeof fn !== 'function') { return; }
        setTimeout(function () { try { fn(); } catch (e) {} }, 1);
    };
    var Fab = function () { this._ok = []; };
    var p = Fab.prototype;
    p.setOption = function () { return this; };
    p.check = function () {
        var l = this._ok.slice();
        for (var i = 0; i < l.length; i++) { later(l[i]); }
        return true;
    };
    p.emitEvent = function (detected) {
        if (detected === false) {
            var l = this._ok.slice();
            for (var i = 0; i < l.length; i++) { later(l[i]); }
        }
        return this;
    };
    p.clearEvent = function () { this._ok = []; };
    p.on = function (detected, fn) {
        if (!detected && typeof fn === 'function') { this._ok.push(fn); later(fn); }
        return this;
    };
    p.onDetected = function () { return this; };
    p.onNotDetected = function (fn) {
        if (typeof fn === 'function') { this._ok.push(fn); later(fn); }
        return this;
    };
    var inst = new Fab();
    var define = function (name, value) {
        try {
            Object.defineProperty(w, name, {
                get: function () { return value; },
                set: function () {},
                configurable: true,
                enumerable: true
            });
        } catch (e) {}
    };
    define('FuckAdBlock', Fab);
    define('BlockAdBlock', Fab);
    define('SniffAdBlock', Fab);
    define('fuckAdBlock', inst);
    define('blockAdBlock', inst);
    define('sniffAdBlock', inst);
})();
