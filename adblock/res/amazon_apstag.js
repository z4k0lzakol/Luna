(function () {
    'use strict';
    var w = window;
    var a = w.apstag;
    if (a === null || typeof a !== 'object') { a = {}; }
    var cbk = function (fn, arg) {
        if (typeof fn !== 'function') { return; }
        setTimeout(function () { try { fn(arg); } catch (e) {} }, 0);
    };
    var noop = function () {};
    a.init = function (cfg, cb) { cbk(cb); };
    a.fetchBids = function (cfg, cb) { cbk(cb, []); };
    a.setDisplayBids = noop;
    a.targetingKeys = function () { return []; };
    a.deleteId = function (cfg, cb) { cbk(cb); };
    a.renewId = function (cfg, cb) { cbk(cb); };
    a.rpa = function (cfg, cb) { cbk(cb); };
    a.upa = function (cfg, cb) { cbk(cb); };
    a.dpa = function (cb) { cbk(cb); };
    a.debug = noop;
    a.punt = noop;
    var run = function (e) {
        if (!e || typeof e !== 'object') { return; }
        var args = Array.prototype.slice.call(e[1] || []);
        if (e[0] === 'i') { a.init.apply(a, args); }
        else if (e[0] === 'f') { a.fetchBids.apply(a, args); }
    };
    var q = Array.isArray(a._Q) ? a._Q : [];
    var pending = q.slice();
    q.length = 0;
    Object.defineProperty(q, 'push', {
        value: function () {
            for (var i = 0; i < arguments.length; i++) { try { run(arguments[i]); } catch (e) {} }
            return this.length;
        },
        writable: true, configurable: true, enumerable: false
    });
    a._Q = q;
    w.apstag = a;
    for (var i = 0; i < pending.length; i++) { try { run(pending[i]); } catch (e) {} }
})();
