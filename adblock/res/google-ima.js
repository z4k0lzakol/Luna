(function () {
    'use strict';
    var w = window;
    var g = w.google;
    if (g === null || (typeof g !== 'object' && typeof g !== 'function')) { g = w.google = {}; }
    var noop = function () {};
    var later = function (fn) { setTimeout(function () { try { fn(); } catch (e) {} }, 0); };
    var Emitter = function () { this._l = {}; };
    Emitter.prototype.addEventListener = function (type, fn, capture, ctx) {
        var types = Array.isArray(type) ? type : [type];
        for (var i = 0; i < types.length; i++) {
            (this._l[types[i]] = this._l[types[i]] || []).push({ f: fn, c: ctx });
        }
    };
    Emitter.prototype.removeEventListener = function (type, fn) {
        var types = Array.isArray(type) ? type : [type];
        for (var i = 0; i < types.length; i++) {
            var l = this._l[types[i]];
            if (!l) { continue; }
            for (var j = l.length - 1; j >= 0; j--) { if (l[j].f === fn) { l.splice(j, 1); } }
        }
    };
    Emitter.prototype._emit = function (ev) {
        var l = (this._l[ev.type] || []).slice();
        for (var i = 0; i < l.length; i++) {
            var h = l[i];
            try {
                if (typeof h.f === 'function') { h.f.call(h.c || null, ev); }
                else if (h.f && typeof h.f.handleEvent === 'function') { h.f.handleEvent(ev); }
            } catch (e) {}
        }
    };
    var inherit = function (C) { C.prototype = Object.create(Emitter.prototype); C.prototype.constructor = C; };

    var ImaSdkSettings = function () {
        this._v = {
            locale: 'en', numRedirects: 4, playerType: '', playerVersion: '', ppid: '', sessionId: '',
            vpaidMode: 0, vpaidAllowed: true, autoPlayAdBreaks: true, cookiesEnabled: true,
            disableCustomPlaybackForIOS10Plus: false, featureFlags: {}, companionBackfill: 'always'
        };
    };
    ['Locale', 'NumRedirects', 'PlayerType', 'PlayerVersion', 'Ppid', 'SessionId', 'VpaidMode',
        'VpaidAllowed', 'AutoPlayAdBreaks', 'CookiesEnabled', 'DisableCustomPlaybackForIOS10Plus',
        'FeatureFlags', 'CompanionBackfill'].forEach(function (n) {
        var k = n.charAt(0).toLowerCase() + n.slice(1);
        ImaSdkSettings.prototype['set' + n] = function (v) { this._v[k] = v; };
        ImaSdkSettings.prototype['get' + n] = function () { return this._v[k]; };
    });
    ImaSdkSettings.prototype.isVpaidAdapter = function () { return false; };
    ImaSdkSettings.prototype.setDisableFlashAds = noop;
    ImaSdkSettings.VpaidMode = { DISABLED: 0, ENABLED: 1, INSECURE: 2 };
    ImaSdkSettings.CompanionBackfillMode = { ALWAYS: 'always', ON_MASTER_AD: 'on_master_ad' };

    var AdDisplayContainer = function (container, video, click) {
        this._c = container || null;
        this._v = video || null;
        this._k = click || null;
    };
    AdDisplayContainer.prototype.initialize = noop;
    AdDisplayContainer.prototype.destroy = noop;

    var AdError = function (msg, code, type, vast, ctx) {
        this.message = msg;
        this._c = code;
        this._t = type;
        this._v = vast;
        this.errorCode = code;
        this.type = type;
    };
    AdError.prototype.getErrorCode = function () { return this._c; };
    AdError.prototype.getVastErrorCode = function () { return this._v; };
    AdError.prototype.getType = function () { return this._t; };
    AdError.prototype.getMessage = function () { return this.message; };
    AdError.prototype.getInnerError = function () { return null; };
    AdError.prototype.toString = function () { return 'AdError ' + this._c + ': ' + this.message; };
    AdError.Type = { AD_LOAD: 'adLoadError', AD_PLAY: 'adPlayError' };
    AdError.ErrorCode = {
        VIDEO_PLAY_ERROR: 400, FAILED_TO_REQUEST_ADS: 1005, REQUIRED_LISTENERS_NOT_ADDED: 900,
        VAST_LOAD_TIMEOUT: 301, VAST_NO_ADS_AFTER_WRAPPER: 303, VAST_MEDIA_LOAD_TIMEOUT: 402,
        VAST_TOO_MANY_REDIRECTS: 302, VAST_ASSET_MISMATCH: 403, VAST_LINEAR_ASSET_MISMATCH: 403,
        VAST_NONLINEAR_ASSET_MISMATCH: 503, VAST_ASSET_NOT_FOUND: 1007, VAST_UNSUPPORTED_VERSION: 102,
        VAST_SCHEMA_VALIDATION_ERROR: 101, VAST_TRAFFICKING_ERROR: 200, VAST_UNEXPECTED_LINEARITY: 201,
        VAST_UNEXPECTED_DURATION_ERROR: 202, VAST_WRAPPER_ERROR: 300, NONLINEAR_DIMENSIONS_ERROR: 501,
        COMPANION_REQUIRED_ERROR: 602, VAST_EMPTY_RESPONSE: 1009, UNSUPPORTED_LOCALE: 1011,
        INVALID_ADX_EXTENSION: 1105, INVALID_ARGUMENTS: 1101, UNKNOWN_AD_RESPONSE: 1010,
        UNKNOWN_ERROR: 900, OVERLAY_AD_PLAYING_FAILED: 500, VAST_MALFORMED_RESPONSE: 100, AUTOPLAY_DISALLOWED: 1205,
        CONSENT_MANAGEMENT_PROVIDER_NOT_READY: 1300, STREAM_INITIALIZATION_FAILED: 1020,
        ADS_REQUEST_NETWORK_ERROR: 1012, INVALID_AD_TAG: 1013, PLAYLIST_NO_CONTENT_TRACKING: 1006
    };

    var AdErrorEvent = function (err, ctx) {
        this.type = AdErrorEvent.Type.AD_ERROR;
        this._e = err;
        this._x = ctx;
    };
    AdErrorEvent.prototype.getError = function () { return this._e; };
    AdErrorEvent.prototype.getUserRequestContext = function () { return this._x; };
    AdErrorEvent.Type = { AD_ERROR: 'adError' };

    var AdEvent = function (type, ad, data) {
        this.type = type;
        this._a = ad || null;
        this._d = data || null;
    };
    AdEvent.prototype.getAd = function () { return this._a; };
    AdEvent.prototype.getAdData = function () { return this._d; };
    AdEvent.Type = {
        AD_BREAK_READY: 'adBreakReady', AD_BREAK_FETCH_ERROR: 'adBreakFetchError',
        AD_BUFFERING: 'adBuffering', AD_CAN_PLAY: 'adCanPlay', AD_METADATA: 'adMetadata',
        AD_PROGRESS: 'adProgress', ALL_ADS_COMPLETED: 'allAdsCompleted', CLICK: 'click',
        COMPLETE: 'complete', CONTENT_PAUSE_REQUESTED: 'contentPauseRequested',
        CONTENT_RESUME_REQUESTED: 'contentResumeRequested', DURATION_CHANGE: 'durationChange',
        FIRST_QUARTILE: 'firstQuartile', IMPRESSION: 'impression', INTERACTION: 'interaction',
        LINEAR_CHANGED: 'linearChanged', LOADED: 'loaded', LOG: 'log', MIDPOINT: 'midpoint',
        PAUSED: 'pause', RESUMED: 'resume', SKIPPABLE_STATE_CHANGED: 'skippableStateChanged',
        SKIPPED: 'skip', STARTED: 'start', THIRD_QUARTILE: 'thirdQuartile', USER_CLOSE: 'userClose',
        VIDEO_CLICKED: 'videoClicked', VIDEO_ICON_CLICKED: 'videoIconClicked',
        VOLUME_CHANGED: 'volumeChange', VOLUME_MUTED: 'mute', AD_MUTED: 'adMuted'
    };

    var AdsManager = function (ctx) {
        Emitter.call(this);
        this._vol = 1;
        this._x = ctx;
    };
    inherit(AdsManager);
    var am = AdsManager.prototype;
    ['init', 'stop', 'pause', 'resume', 'skip', 'destroy', 'resize', 'discardAdBreak', 'focus',
        'updateAdsRenderingSettings', 'configureAdsManager', 'clicked', 'collapse', 'expand',
        'requestNextAdBreak', 'setAutoPlayAdBreaks'].forEach(function (n) { am[n] = noop; });
    am.start = function () {
        var self = this;
        later(function () {
            self._emit(new AdEvent(AdEvent.Type.CONTENT_RESUME_REQUESTED));
            self._emit(new AdEvent(AdEvent.Type.ALL_ADS_COMPLETED));
        });
    };
    am.getAdSkippableState = function () { return false; };
    am.getCuePoints = function () { return []; };
    am.getCurrentAd = function () { return null; };
    am.getRemainingTime = function () { return 0; };
    am.getVolume = function () { return this._vol; };
    am.setVolume = function (v) { this._vol = v; };
    am.isCustomClickTrackingUsed = function () { return false; };
    am.isCustomPlaybackUsed = function () { return false; };

    var AdsManagerLoadedEvent = function (ctx) {
        this.type = AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED;
        this._x = ctx;
    };
    AdsManagerLoadedEvent.prototype.getAdsManager = function () { return new AdsManager(this._x); };
    AdsManagerLoadedEvent.prototype.getUserRequestContext = function () { return this._x; };
    AdsManagerLoadedEvent.Type = { ADS_MANAGER_LOADED: 'adsManagerLoaded' };

    var settings = new ImaSdkSettings();
    var AdsLoader = function (container) {
        Emitter.call(this);
        this._c = container;
    };
    inherit(AdsLoader);
    AdsLoader.prototype.contentComplete = noop;
    AdsLoader.prototype.destroy = noop;
    AdsLoader.prototype.getSettings = function () { return settings; };
    AdsLoader.prototype.getVersion = function () { return ima.VERSION; };
    AdsLoader.prototype.requestAds = function (req, ctx) {
        var self = this;
        setTimeout(function () {
            var err = new AdError('The VAST response document is empty.', 1009, AdError.Type.AD_LOAD, 303);
            self._emit(new AdErrorEvent(err, ctx));
        }, 5);
    };

    var AdsRequest = function () {
        this.adTagUrl = '';
        this.adsResponse = null;
        this.linearAdSlotWidth = 0;
        this.linearAdSlotHeight = 0;
        this.nonLinearAdSlotWidth = 0;
        this.nonLinearAdSlotHeight = 0;
        this.vastLoadTimeout = 5000;
        this.forceNonLinearFullSlot = false;
        this.omidAccessModeRules = {};
        this.contentDuration = null;
        this.contentKeywords = null;
        this.contentTitle = null;
        this.liveStreamPrefetchSeconds = 0;
    };
    AdsRequest.prototype.setAdWillAutoPlay = function (v) { this._ap = v; };
    AdsRequest.prototype.setAdWillPlayMuted = function (v) { this._pm = v; };
    AdsRequest.prototype.setContinuousPlayback = function (v) { this._cp = v; };

    var AdsRenderingSettings = function () {
        this.autoAlign = true;
        this.bitrate = -1;
        this.enablePreloading = false;
        this.loadVideoTimeout = -1;
        this.mimeTypes = null;
        this.playAdsAfterTime = -1;
        this.restoreCustomPlaybackStateOnAdBreakComplete = false;
        this.uiElements = null;
        this.useStyledLinearAds = false;
        this.useStyledNonLinearAds = false;
    };

    var CompanionAdSelectionSettings = function () {
        this.creativeType = 'All';
        this.resourceType = 'All';
        this.sizeCriteria = 'SelectExactMatch';
    };
    CompanionAdSelectionSettings.CreativeType = { ALL: 'All', FLASH: 'Flash', IMAGE: 'Image' };
    CompanionAdSelectionSettings.ResourceType = { ALL: 'All', HTML: 'Html', IFRAME: 'IFrame', STATIC: 'Static' };
    CompanionAdSelectionSettings.SizeCriteria = { IGNORE: 'IgnoreSize', SELECT_EXACT_MATCH: 'SelectExactMatch', SELECT_NEAR_MATCH: 'SelectNearMatch', SELECT_FLUID: 'SelectFluid' };

    var ima = {
        VERSION: '3.700.0',
        settings: settings,
        AdDisplayContainer: AdDisplayContainer,
        AdsLoader: AdsLoader,
        AdsManager: AdsManager,
        AdsRequest: AdsRequest,
        AdsRenderingSettings: AdsRenderingSettings,
        ImaSdkSettings: ImaSdkSettings,
        CompanionAdSelectionSettings: CompanionAdSelectionSettings,
        AdError: AdError,
        AdErrorEvent: AdErrorEvent,
        AdEvent: AdEvent,
        AdsManagerLoadedEvent: AdsManagerLoadedEvent,
        ViewMode: { NORMAL: 'normal', FULLSCREEN: 'fullscreen' },
        UiElements: { AD_ATTRIBUTION: 'adAttribution', COUNTDOWN: 'countdown' },
        OmidAccessMode: { LIMITED: 'limited', DOMAIN: 'domain', FULL: 'full' },
        OmidVerificationVendor: {
            COMSCORE: 7, DOUBLEVERIFY: 3, GOOGLE: 9, INTEGRAL_AD_SCIENCE: 4, MEETRICS: 8,
            MOAT: 2, NIELSEN: 6, PIXELATE: 5, OTHER: 1
        },
        AdsRequestOptions: {}
    };
    g.ima = ima;
})();
