(function () {
    'use strict';
    var w = window;
    var later = function (fn) { setTimeout(function () { try { fn(); } catch (e) {} }, 0); };
    var names = ['_addIgnoredOrganic', '_addIgnoredRef', '_addItem', '_addOrganic', '_addTrans',
        '_clearIgnoredOrganic', '_clearIgnoredRef', '_clearOrganic', '_clearTrans', '_clearXKey', '_clearXValue',
        '_cookiePathCopy', '_deleteCustomVar', '_getClientInfo', '_getDetectFlash', '_getDetectTitle',
        '_getLocalGifPath', '_getServiceMode', '_getVersion', '_getVisitorCustomVar', '_getXKey',
        '_getXValue', '_initData', '_require', '_setAllowAnchor', '_setAllowHash', '_setAllowLinker',
        '_setCampContentKey', '_setCampMediumKey', '_setCampNameKey', '_setCampNOKey',
        '_setCampSourceKey', '_setCampTermKey', '_setCampaignCookieTimeout', '_setCampaignTrack',
        '_setClientInfo', '_setCookiePath', '_setCookiePersistence', '_setCookieTimeout',
        '_setCustomVar', '_setDetectFlash', '_setDetectTitle', '_setDomainName', '_setLocalGifPath',
        '_setLocalRemoteServerMode', '_setLocalServerMode', '_setMaxCustomVariables',
        '_setNamespace', '_setReferrerOverride', '_setRemoteServerMode', '_setSampleRate',
        '_setSessionCookieTimeout', '_setSessionTimeout', '_setSiteSpeedSampleRate', '_setTrans',
        '_setTransactionDelim', '_setVar', '_setVisitorCookieTimeout', '_setXKey', '_setXValue',
        '_trackPageLoadTime', '_trackSocial', '_trackTiming', '_trackTrans', '_visitCode'];
    var noop = function () {};
    var Tracker = function (acct, name) {
        this._acct = acct === undefined ? 'UA-XXXXX-X' : String(acct);
        this._name = name === undefined ? '' : String(name);
        this._cb = null;
    };
    var tp = Tracker.prototype;
    for (var i = 0; i < names.length; i++) { tp[names[i]] = noop; }
    tp._getVersion = function () { return '5.7.2'; };
    tp._getName = function () { return this._name; };
    tp._getAccount = function () { return this._acct; };
    tp._setAccount = function (a) { this._acct = String(a); };
    tp._getLinkerUrl = function (u) { return u; };
    tp._link = function (u) { if (typeof u === 'string' && u) { w.location.href = u; } };
    tp._linkByPost = function () { return true; };
    tp._getVisitorCustomVar = function () { return undefined; };
    tp._set = function (k, v) { if (k === 'hitCallback') { this._cb = typeof v === 'function' ? v : null; } };
    var hit = function () {
        var cb = this._cb;
        if (cb) { this._cb = null; later(cb); }
    };
    tp._trackPageview = hit;
    tp._trackEvent = function () { hit.call(this); return true; };
    var trackers = {};
    var get = function (name, acct) {
        var k = name === undefined ? '' : String(name);
        if (!trackers[k]) { trackers[k] = new Tracker(acct, k); }
        else if (acct !== undefined) { trackers[k]._acct = String(acct); }
        return trackers[k];
    };
    var gat = {
        _getTracker: function (acct) { return new Tracker(acct, '~' + Object.keys(trackers).length); },
        _createTracker: function (acct, name) { return get(name === undefined ? '~' + Object.keys(trackers).length : name, acct); },
        _getTrackerByName: function (name) { return get(name); },
        _anonymizeIp: noop,
        _forceSSL: noop,
        _getVersion: function () { return '5.7.2'; }
    };
    var run = function (item) {
        if (typeof item === 'function') { try { item.call(w); } catch (e) {} return; }
        if (!Array.isArray(item) || typeof item[0] !== 'string') { return; }
        var m = /^(?:([^.]+)\.)?(_\w+)$/.exec(item[0]);
        if (!m) { return; }
        var t = get(m[1] === undefined ? '' : m[1]);
        var f = t[m[2]];
        if (typeof f === 'function') { try { f.apply(t, item.slice(1)); } catch (e) {} }
    };
    var old = w._gaq;
    var q = {
        push: function () {
            for (var i = 0; i < arguments.length; i++) { run(arguments[i]); }
            return 0;
        },
        _createAsyncTracker: function (acct, name) { return get(name, acct); },
        _getAsyncTracker: function (name) { return get(name); }
    };
    w._gat = gat;
    w._gaq = q;
    if (Array.isArray(old)) {
        for (var j = 0; j < old.length; j++) { run(old[j]); }
    }
})();
