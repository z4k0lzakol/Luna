(function () {
    'use strict';
    var w = window;
    var gt = w.googletag;
    if (gt === null || (typeof gt !== 'object' && typeof gt !== 'function')) { gt = {}; }
    var noop = function () {};
    var later = function (fn) { setTimeout(function () { try { fn(); } catch (e) {} }, 0); };
    var slots = [];
    var state = { enabled: false, collapse: false, initialLoadDisabled: false };
    var listeners = {};
    var emit = function (type, ev) {
        var list = listeners[type];
        if (!list) { return; }
        list = list.slice();
        for (var i = 0; i < list.length; i++) {
            try { list[i].call(w, ev); } catch (e) {}
        }
    };
    var render = function (slot) {
        later(function () {
            emit('slotRequested', { slot: slot, serviceName: 'publisher_ads' });
            emit('slotResponseReceived', { slot: slot, serviceName: 'publisher_ads' });
            emit('slotRenderEnded', {
                slot: slot, isEmpty: true, size: null, creativeId: null, lineItemId: null,
                advertiserId: null, campaignId: null, sourceAgnosticCreativeId: null,
                sourceAgnosticLineItemId: null, isBackfill: false, companyIds: [], labelIds: [],
                yieldGroupIds: [], serviceName: 'publisher_ads', slotContentChanged: false
            });
            if (state.collapse) {
                var el = document.getElementById(slot.getSlotElementId());
                if (el) { el.style.display = 'none'; }
            }
        });
    };
    var targetingApi = function (obj) {
        obj.setTargeting = function (k, v) {
            this._t[k] = Array.isArray(v) ? v.map(String) : [String(v)];
            return this;
        };
        obj.getTargeting = function (k) { return this._t[k] ? this._t[k].slice() : []; };
        obj.getTargetingKeys = function () { return Object.keys(this._t); };
        obj.clearTargeting = function (k) {
            if (k === undefined) { this._t = {}; } else { delete this._t[k]; }
            return this;
        };
        obj.updateTargetingFromMap = function (m) {
            if (m && typeof m === 'object') {
                for (var k in m) { if (Object.prototype.hasOwnProperty.call(m, k)) { this.setTargeting(k, m[k]); } }
            }
            return this;
        };
    };
    var Slot = function (path, sizes, divId) {
        this._p = String(path);
        this._s = sizes;
        this._d = divId === undefined || divId === null ? 'gpt_unit_' + this._p + '_' + slots.length : String(divId);
        this._t = {};
        this._a = {};
        this._x = [];
        this._sv = [];
    };
    targetingApi(Slot.prototype);
    var sp = Slot.prototype;
    var self = function () { return this; };
    sp.addService = function (s) { if (this._sv.indexOf(s) < 0) { this._sv.push(s); } return this; };
    sp.clearCategoryExclusions = function () { this._x = []; return this; };
    sp.setCategoryExclusion = function (c) { this._x.push(String(c)); return this; };
    sp.getCategoryExclusions = function () { return this._x.slice(); };
    sp.defineSizeMapping = self;
    sp.set = function (k, v) { this._a[k] = v; return this; };
    sp.get = function (k) { return Object.prototype.hasOwnProperty.call(this._a, k) ? this._a[k] : null; };
    sp.getAttributeKeys = function () { return Object.keys(this._a); };
    sp.setClickUrl = self;
    sp.setCollapseEmptyDiv = self;
    sp.setConfig = self;
    sp.setForceSafeFrame = self;
    sp.setSafeFrameConfig = self;
    sp.getAdUnitPath = function () { return this._p; };
    sp.getDomId = function () { return this._d; };
    sp.getSlotElementId = function () { return this._d; };
    sp.getSlotId = function () {
        var s = this;
        return {
            getId: function () { return s._p + '_0'; },
            getAdUnitPath: function () { return s._p; },
            getDomId: function () { return s._d; },
            getName: function () { return s._p; }
        };
    };
    sp.getResponseInformation = function () { return null; };
    sp.getSizes = function () { return []; };
    sp.getServices = function () { return this._sv.slice(); };
    sp.getEscapedQemQueryId = function () { return ''; };
    sp.getHtml = function () { return ''; };
    var Passback = function () { this._t = {}; };
    targetingApi(Passback.prototype);
    Passback.prototype.display = noop;
    Passback.prototype.setClickUrl = self;
    Passback.prototype.setForceSafeFrame = self;
    Passback.prototype.set = self;
    var Service = function () { this._t = {}; this._a = {}; this._x = []; };
    targetingApi(Service.prototype);
    var vp = Service.prototype;
    vp.addEventListener = function (type, fn) {
        if (typeof fn === 'function') { (listeners[type] = listeners[type] || []).push(fn); }
        return this;
    };
    vp.removeEventListener = function (type, fn) {
        var list = listeners[type];
        if (list) { var i = list.indexOf(fn); if (i >= 0) { list.splice(i, 1); return true; } }
        return false;
    };
    vp.getSlots = function () { return slots.slice(); };
    vp.getSlotIdMap = function () {
        var m = {};
        slots.forEach(function (s) { m[s.getAdUnitPath() + '_0'] = s; });
        return m;
    };
    vp.refresh = function (list) {
        if (!state.enabled) { return; }
        (Array.isArray(list) ? list : slots).forEach(function (s) { if (s instanceof Slot) { render(s); } });
    };
    vp.clear = function () { return true; };
    vp.collapseEmptyDivs = function () { state.collapse = true; return true; };
    vp.disableInitialLoad = function () { state.initialLoadDisabled = true; };
    vp.isInitialLoadDisabled = function () { return state.initialLoadDisabled; };
    vp.display = function (path, size, div) {
        var s = gt.defineSlot(path, size, div);
        s.addService(this);
        gt.display(s);
    };
    vp.enableAsyncRendering = function () { return true; };
    vp.enableLazyLoad = noop;
    vp.enableSingleRequest = function () { return true; };
    vp.enableSyncRendering = function () { return true; };
    vp.enableVideoAds = noop;
    vp.set = function (k, v) { this._a[k] = v; return this; };
    vp.get = function (k) { return Object.prototype.hasOwnProperty.call(this._a, k) ? this._a[k] : null; };
    vp.getAttributeKeys = function () { return Object.keys(this._a); };
    vp.setCategoryExclusion = function (c) { this._x.push(String(c)); return this; };
    vp.clearCategoryExclusions = function () { this._x = []; return this; };
    ['setCentering', 'setCookieOptions', 'setForceSafeFrame', 'setLocation', 'setPrivacySettings',
        'setPublisherProvidedId', 'setRequestNonPersonalizedAds', 'setSafeFrameConfig',
        'setTagForChildDirectedTreatment', 'setTagForUnderAgeOfConsent', 'setVideoContent',
        'updateCorrelator', 'setConfig', 'setRefreshUnfilledSlots', 'setVideoContentInformation'].forEach(function (n) { vp[n] = self; });
    vp.definePassback = function () { return new Passback(); };
    vp.defineOutOfPagePassback = function () { return new Passback(); };
    vp.getName = function () { return 'publisher_ads'; };
    vp.getVideoContent = function () { return null; };
    vp.getCorrelator = function () { return String(Math.floor(Math.random() * 9e15) + 1e15); };
    vp.setRefreshUnfilledSlots = self;
    vp.notifyUnfilledSlots = noop;
    vp.isSRA = function () { return false; };
    vp.onGoogleAdsJsLoad = noop;
    vp.fillSlot = noop;
    vp.setVideoSession = noop;
    var pubads = new Service();
    var companion = new Service();
    companion.getName = function () { return 'companion_ads'; };
    companion.setRefreshUnfilledSlots = self;
    companion.isRoadblockingSupported = function () { return false; };
    var content = new Service();
    content.getName = function () { return 'content'; };
    content.setContent = noop;
    gt.pubads = function () { return pubads; };
    gt.companionAds = function () { return companion; };
    gt.content = function () { return content; };
    gt.defineSlot = function (path, size, div) {
        var s = new Slot(path, size, div);
        slots.push(s);
        return s;
    };
    gt.defineOutOfPageSlot = function (path, div) {
        var s = new Slot(path, [], typeof div === 'string' ? div : null);
        slots.push(s);
        return s;
    };
    gt.destroySlots = function (list) {
        if (Array.isArray(list)) {
            list.forEach(function (s) { var i = slots.indexOf(s); if (i >= 0) { slots.splice(i, 1); } });
        } else { slots.length = 0; }
        return true;
    };
    gt.display = function (arg) {
        var found = [];
        if (arg instanceof Slot) { found.push(arg); }
        else {
            var id = arg && typeof arg === 'object' && arg.id !== undefined ? arg.id : arg;
            slots.forEach(function (s) { if (s.getSlotElementId() === String(id)) { found.push(s); } });
        }
        if (!state.enabled || state.initialLoadDisabled) { return; }
        found.forEach(render);
    };
    gt.enableServices = function () { state.enabled = true; };
    gt.disablePublisherConsole = noop;
    gt.openConsole = noop;
    gt.setAdIframeTitle = noop;
    gt.setConfig = noop;
    gt.getConfig = function () { return {}; };
    gt.getVersion = function () { return '2025101001'; };
    gt.sizeMapping = function () {
        return { addSize: function () { return this; }, build: function () { return []; } };
    };
    gt.evalScripts = noop;
    gt.getEventLog = function () {
        return { getAllEvents: function () { return []; }, getEventsBySlot: function () { return []; }, getEventsByLevel: function () { return []; } };
    };
    gt.enums = {
        OutOfPageFormat: { TOP_ANCHOR: 2, BOTTOM_ANCHOR: 3, REWARDED: 4, INTERSTITIAL: 5, LEFT_SIDE_RAIL: 6, RIGHT_SIDE_RAIL: 7, GAME_MANUAL_INTERSTITIAL: 8 },
        TrafficSource: { ORGANIC: 0, PURCHASED: 1 }
    };
    gt.apiReady = true;
    gt.pubadsReady = true;
    var queue = function (old) {
        var q = {
            push: function () {
                for (var i = 0; i < arguments.length; i++) {
                    var f = arguments[i];
                    if (typeof f === 'function') { try { f.call(w); } catch (e) {} }
                }
                return 1;
            }
        };
        if (Array.isArray(old)) { q.push.apply(q, old); }
        return q;
    };
    gt.secureSignalProviders = { push: function () { return 1; }, clearAllCache: noop };
    w.googletag = gt;
    gt.cmd = queue(gt.cmd);
})();
