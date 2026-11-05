(function () {
    'use strict';
    var w = window;
    var name = typeof w.GoogleAnalyticsObject === 'string' && w.GoogleAnalyticsObject ? w.GoogleAnalyticsObject : 'ga';
    var old = w[name];
    if (typeof old === 'function' && old.loaded === true && typeof old.getAll === 'function') { return; }
    var later = function (fn, arg) {
        setTimeout(function () { try { fn(arg); } catch (e) {} }, 0);
    };
    var cid = String(Math.floor(Math.random() * 2147483647)) + '.' + String(Math.floor(Date.now() / 1000));
    var trackers = [];
    var byName = {};
    var Tracker = function (fields) {
        this._f = { name: 't0', clientId: cid, cookieDomain: 'auto', apiVersion: '1', hitCallback: null };
        for (var k in fields) {
            if (Object.prototype.hasOwnProperty.call(fields, k) && fields[k] !== undefined) { this._f[k] = fields[k]; }
        }
    };
    Tracker.prototype.get = function (k) {
        return Object.prototype.hasOwnProperty.call(this._f, k) ? this._f[k] : undefined;
    };
    Tracker.prototype.set = function (k, v) {
        if (k && typeof k === 'object') {
            for (var x in k) { if (Object.prototype.hasOwnProperty.call(k, x)) { this._f[x] = k[x]; } }
        } else if (typeof k === 'string') { this._f[k] = v; }
    };
    Tracker.prototype.send = function () {
        var cb = null;
        for (var i = arguments.length - 1; i >= 0; i--) {
            var a = arguments[i];
            if (a && typeof a === 'object' && typeof a.hitCallback === 'function') { cb = a.hitCallback; break; }
        }
        if (!cb && typeof this._f.hitCallback === 'function') { cb = this._f.hitCallback; }
        if (cb) { later(cb); }
    };
    Tracker.prototype.require = function () {};
    Tracker.prototype.provide = function () {};
    var create = function (id, a, b, c) {
        var f = {};
        var add = function (o) {
            if (o && typeof o === 'object') { for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k)) { f[k] = o[k]; } } }
        };
        if (id && typeof id === 'object') { add(id); }
        else {
            f.trackingId = id;
            if (a && typeof a === 'object') { add(a); }
            else {
                if (a !== undefined) { f.cookieDomain = a; }
                if (b && typeof b === 'object') { add(b); }
                else {
                    if (b !== undefined) { f.name = b; }
                    add(c);
                }
            }
        }
        var t = new Tracker(f);
        var n = t.get('name');
        if (byName[n]) { return byName[n]; }
        byName[n] = t;
        trackers.push(t);
        return t;
    };
    var ga = function () {
        var args = Array.prototype.slice.call(arguments);
        var cmd = args[0];
        if (typeof cmd === 'function') {
            later(cmd, byName.t0 || trackers[0]);
            return;
        }
        if (typeof cmd !== 'string') { return; }
        var m = /^(?:([\w-]+)\.)?([\w:.]+)$/.exec(cmd);
        if (!m) { return; }
        var tname = m[1] || 't0';
        var method = m[2];
        if (method === 'create') { create.apply(null, args.slice(1)); return; }
        if (method === 'remove') { ga.remove(tname); return; }
        if (method === 'provide' || method === 'require' || method.indexOf(':') >= 0) { return; }
        var t = byName[tname];
        if (!t) { return; }
        if (method === 'send') { t.send.apply(t, args.slice(1)); }
        else if (method === 'set') { t.set(args[1], args[2]); }
    };
    ga.create = function () { return create.apply(null, arguments); };
    ga.getByName = function (n) { return byName[n] || null; };
    ga.getAll = function () { return trackers.slice(); };
    ga.remove = function (n) {
        var t = byName[n];
        if (!t) { return; }
        delete byName[n];
        var i = trackers.indexOf(t);
        if (i >= 0) { trackers.splice(i, 1); }
    };
    ga.loaded = true;
    ga.answer = 42;
    ga.l = old && old.l ? old.l : Date.now();
    var Linker = function () {};
    Linker.prototype.autoLink = function () {};
    Linker.prototype.decorate = function (u) { return u; };
    Linker.prototype.passthrough = function (u) { return u; };
    w.gaplugins = w.gaplugins || {};
    w.gaplugins.Linker = Linker;
    var q = old && Array.isArray(old.q) ? old.q : [];
    w[name] = ga;
    for (var i = 0; i < q.length; i++) {
        try { ga.apply(null, q[i]); } catch (e) {}
    }
})();
