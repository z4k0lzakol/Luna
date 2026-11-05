// @world: main
// google-ima (google-ima3): IMA SDK HTML5 shim injected at document start. Spec 03c 14, 04 5.3.
// Players see a loaded SDK and a genuine "no fill": AdsLoader.requestAds() asynchronously dispatches adError with
// AdError 1009 (VAST 303, adLoadError) and the user request context, so they resume content. AdsManager stub
// (start() -> contentResumeRequested + allAdsCompleted) for players that get one anyway.
// google.ima is a trap: it survives `window.google = ...` replacements (a deferred chain re-installs it on every
// new google object); same-type writes to google.ima are ignored. Exposed functions print as "function () {}".
function (R, ...args) {
  var n = R.n, win = R.win;
  var isArray = n.isArray, aSplice = n.aSplice;
  var noop = R.fn(R.anon(function () {}), "function () {}");
  function pub(f) { return R.fn(f, "function () {}"); }
  function later(fn, ms) { R.later(fn, ms || 0); }
  function listOf(type) { return isArray(type) ? R.toArray(type) : [type]; }

  var Emitter = pub(R.anon(function () { this._l = n.create(null); }));
  Emitter.prototype.addEventListener = pub(R.anon(function (type, fn, capture, ctx) {
    var t = listOf(type);
    for (var i = 0; i < t.length; i++) {
      var k = R.str(t[i]), l = this._l[k];
      if (!l) l = this._l[k] = [];
      R.push(l, { f: fn, c: ctx });
    }
  }));
  Emitter.prototype.removeEventListener = pub(R.anon(function (type, fn) {
    var t = listOf(type);
    for (var i = 0; i < t.length; i++) {
      var l = this._l[R.str(t[i])];
      if (!l) continue;
      for (var j = l.length - 1; j >= 0; j--) if (l[j].f === fn) R.apply(aSplice, l, [j, 1]);
    }
  }));
  function emit(target, ev) {
    var l = target._l && target._l[ev.type];
    if (!l) return;
    l = R.toArray(l);
    for (var i = 0; i < l.length; i++) {
      var h = l[i];
      try {
        if (typeof h.f === "function") R.apply(h.f, h.c === undefined ? null : h.c, [ev]);
        else if (R.isObj(h.f) && typeof h.f.handleEvent === "function") R.apply(h.f.handleEvent, h.f, [ev]);
      } catch (e) { /* ignore */ }
    }
  }
  function inherit(C) {
    C.prototype = n.create(Emitter.prototype);
    n.defineProperty(C.prototype, "constructor", { value: C, writable: true, enumerable: false, configurable: true });
  }

  var SETTINGS = ["Locale", "NumRedirects", "PlayerType", "PlayerVersion", "Ppid", "SessionId", "VpaidMode",
    "VpaidAllowed", "AutoPlayAdBreaks", "CookiesEnabled", "DisableCustomPlaybackForIOS10Plus", "FeatureFlags",
    "CompanionBackfill"];
  var ImaSdkSettings = pub(R.anon(function () {
    this._v = { locale: "en", numRedirects: 4, playerType: "", playerVersion: "", ppid: "", sessionId: "",
      vpaidMode: 0, vpaidAllowed: true, autoPlayAdBreaks: true, cookiesEnabled: true,
      disableCustomPlaybackForIOS10Plus: false, featureFlags: {}, companionBackfill: "always" };
  }));
  for (var si = 0; si < SETTINGS.length; si++) {
    (function (nm) {
      var k = R.lower(R.slice(nm, 0, 1)) + R.slice(nm, 1);
      ImaSdkSettings.prototype["set" + nm] = pub(R.anon(function (v) { this._v[k] = v; }));
      ImaSdkSettings.prototype["get" + nm] = pub(R.anon(function () { return this._v[k]; }));
    })(SETTINGS[si]);
  }
  ImaSdkSettings.prototype.isVpaidAdapter = pub(R.anon(function () { return false; }));
  ImaSdkSettings.prototype.setDisableFlashAds = noop;
  ImaSdkSettings.VpaidMode = { DISABLED: 0, ENABLED: 1, INSECURE: 2 };
  ImaSdkSettings.CompanionBackfillMode = { ALWAYS: "always", ON_MASTER_AD: "on_master_ad" };

  var AdDisplayContainer = pub(R.anon(function (container, video, click) {
    this._c = container || null; this._v = video || null; this._k = click || null;
  }));
  AdDisplayContainer.prototype.initialize = noop;
  AdDisplayContainer.prototype.destroy = noop;

  var AdError = pub(R.anon(function (msg, code, type, vast) {
    this.message = msg; this.errorCode = code; this.type = type; this._v = vast;
  }));
  AdError.prototype.getErrorCode = pub(R.anon(function () { return this.errorCode; }));
  AdError.prototype.getVastErrorCode = pub(R.anon(function () { return this._v; }));
  AdError.prototype.getType = pub(R.anon(function () { return this.type; }));
  AdError.prototype.getMessage = pub(R.anon(function () { return this.message; }));
  AdError.prototype.getInnerError = pub(R.anon(function () { return null; }));
  AdError.prototype.toString = pub(R.anon(function () { return "AdError " + this.errorCode + ": " + this.message; }));
  AdError.Type = { AD_LOAD: "adLoadError", AD_PLAY: "adPlayError" };
  AdError.ErrorCode = {
    VIDEO_PLAY_ERROR: 400, FAILED_TO_REQUEST_ADS: 1005, REQUIRED_LISTENERS_NOT_ADDED: 900,
    VAST_LOAD_TIMEOUT: 301, VAST_NO_ADS_AFTER_WRAPPER: 303, VAST_MEDIA_LOAD_TIMEOUT: 402,
    VAST_TOO_MANY_REDIRECTS: 302, VAST_ASSET_MISMATCH: 403, VAST_LINEAR_ASSET_MISMATCH: 403,
    VAST_NONLINEAR_ASSET_MISMATCH: 503, VAST_ASSET_NOT_FOUND: 1007, VAST_UNSUPPORTED_VERSION: 102,
    VAST_SCHEMA_VALIDATION_ERROR: 101, VAST_TRAFFICKING_ERROR: 200, VAST_UNEXPECTED_LINEARITY: 201,
    VAST_UNEXPECTED_DURATION_ERROR: 202, VAST_WRAPPER_ERROR: 300, NONLINEAR_DIMENSIONS_ERROR: 501,
    COMPANION_REQUIRED_ERROR: 602, VAST_EMPTY_RESPONSE: 1009, UNSUPPORTED_LOCALE: 1011,
    INVALID_ADX_EXTENSION: 1105, INVALID_ARGUMENTS: 1101, UNKNOWN_AD_RESPONSE: 1010,
    UNKNOWN_ERROR: 900, OVERLAY_AD_PLAYING_FAILED: 500, VAST_MALFORMED_RESPONSE: 100,
    AUTOPLAY_DISALLOWED: 1205, CONSENT_MANAGEMENT_PROVIDER_NOT_READY: 1300,
    STREAM_INITIALIZATION_FAILED: 1020, ADS_REQUEST_NETWORK_ERROR: 1012, INVALID_AD_TAG: 1013,
    PLAYLIST_NO_CONTENT_TRACKING: 1006
  };

  var AdErrorEvent = pub(R.anon(function (err, ctx) { this.type = "adError"; this._e = err; this._x = ctx; }));
  AdErrorEvent.prototype.getError = pub(R.anon(function () { return this._e; }));
  AdErrorEvent.prototype.getUserRequestContext = pub(R.anon(function () { return this._x; }));
  AdErrorEvent.Type = { AD_ERROR: "adError" };

  var AdEvent = pub(R.anon(function (type, ad, data) { this.type = type; this._a = ad || null; this._d = data || null; }));
  AdEvent.prototype.getAd = pub(R.anon(function () { return this._a; }));
  AdEvent.prototype.getAdData = pub(R.anon(function () { return this._d; }));
  AdEvent.Type = {
    AD_BREAK_READY: "adBreakReady", AD_BREAK_FETCH_ERROR: "adBreakFetchError", AD_BUFFERING: "adBuffering",
    AD_CAN_PLAY: "adCanPlay", AD_METADATA: "adMetadata", AD_PROGRESS: "adProgress",
    ALL_ADS_COMPLETED: "allAdsCompleted", CLICK: "click", COMPLETE: "complete",
    CONTENT_PAUSE_REQUESTED: "contentPauseRequested", CONTENT_RESUME_REQUESTED: "contentResumeRequested",
    DURATION_CHANGE: "durationChange", FIRST_QUARTILE: "firstQuartile", IMPRESSION: "impression",
    INTERACTION: "interaction", LINEAR_CHANGED: "linearChanged", LOADED: "loaded", LOG: "log",
    MIDPOINT: "midpoint", PAUSED: "pause", RESUMED: "resume", SKIPPABLE_STATE_CHANGED: "skippableStateChanged",
    SKIPPED: "skip", STARTED: "start", THIRD_QUARTILE: "thirdQuartile", USER_CLOSE: "userClose",
    VIDEO_CLICKED: "videoClicked", VIDEO_ICON_CLICKED: "videoIconClicked", VOLUME_CHANGED: "volumeChange",
    VOLUME_MUTED: "mute", AD_MUTED: "adMuted"
  };

  var AdsManager = pub(R.anon(function (ctx) { R.apply(Emitter, this, []); this._vol = 1; this._x = ctx; }));
  inherit(AdsManager);
  var am = AdsManager.prototype;
  var NOOPS = ["init", "stop", "pause", "resume", "skip", "destroy", "resize", "discardAdBreak", "focus",
    "updateAdsRenderingSettings", "configureAdsManager", "clicked", "collapse", "expand", "requestNextAdBreak",
    "setAutoPlayAdBreaks"];
  for (var ni = 0; ni < NOOPS.length; ni++) am[NOOPS[ni]] = noop;
  am.start = pub(R.anon(function () {
    var self = this;
    later(function () {
      emit(self, new AdEvent("contentResumeRequested"));
      emit(self, new AdEvent("allAdsCompleted"));
    });
  }));
  am.getAdSkippableState = pub(R.anon(function () { return false; }));
  am.getCuePoints = pub(R.anon(function () { return []; }));
  am.getCurrentAd = pub(R.anon(function () { return null; }));
  am.getRemainingTime = pub(R.anon(function () { return 0; }));
  am.getVolume = pub(R.anon(function () { return this._vol; }));
  am.setVolume = pub(R.anon(function (v) { this._vol = v; }));
  am.isCustomClickTrackingUsed = pub(R.anon(function () { return false; }));
  am.isCustomPlaybackUsed = pub(R.anon(function () { return false; }));

  var AdsManagerLoadedEvent = pub(R.anon(function (ctx) { this.type = "adsManagerLoaded"; this._x = ctx; }));
  AdsManagerLoadedEvent.prototype.getAdsManager = pub(R.anon(function () { return new AdsManager(this._x); }));
  AdsManagerLoadedEvent.prototype.getUserRequestContext = pub(R.anon(function () { return this._x; }));
  AdsManagerLoadedEvent.Type = { ADS_MANAGER_LOADED: "adsManagerLoaded" };

  var settings = new ImaSdkSettings();
  var AdsLoader = pub(R.anon(function (container) { R.apply(Emitter, this, []); this._c = container; }));
  inherit(AdsLoader);
  AdsLoader.prototype.contentComplete = noop;
  AdsLoader.prototype.destroy = noop;
  AdsLoader.prototype.getSettings = pub(R.anon(function () { return settings; }));
  AdsLoader.prototype.getVersion = pub(R.anon(function () { return "3.700.0"; }));
  AdsLoader.prototype.requestAds = pub(R.anon(function (req, ctx) {
    var self = this;
    later(function () {
      emit(self, new AdErrorEvent(new AdError("The VAST response document is empty.", 1009, "adLoadError", 303), ctx));
    }, 5);
  }));

  var AdsRequest = pub(R.anon(function () {
    this.adTagUrl = ""; this.adsResponse = null; this.linearAdSlotWidth = 0; this.linearAdSlotHeight = 0;
    this.nonLinearAdSlotWidth = 0; this.nonLinearAdSlotHeight = 0; this.vastLoadTimeout = 5000;
    this.forceNonLinearFullSlot = false; this.omidAccessModeRules = {}; this.contentDuration = null;
    this.contentKeywords = null; this.contentTitle = null; this.liveStreamPrefetchSeconds = 0;
  }));
  AdsRequest.prototype.setAdWillAutoPlay = pub(R.anon(function (v) { this._ap = v; }));
  AdsRequest.prototype.setAdWillPlayMuted = pub(R.anon(function (v) { this._pm = v; }));
  AdsRequest.prototype.setContinuousPlayback = pub(R.anon(function (v) { this._cp = v; }));

  var AdsRenderingSettings = pub(R.anon(function () {
    this.autoAlign = true; this.bitrate = -1; this.enablePreloading = false; this.loadVideoTimeout = -1;
    this.mimeTypes = null; this.playAdsAfterTime = -1; this.restoreCustomPlaybackStateOnAdBreakComplete = false;
    this.uiElements = null; this.useStyledLinearAds = false; this.useStyledNonLinearAds = false;
  }));

  var CompanionAdSelectionSettings = pub(R.anon(function () {
    this.creativeType = "All"; this.resourceType = "All"; this.sizeCriteria = "SelectExactMatch";
  }));
  CompanionAdSelectionSettings.CreativeType = { ALL: "All", FLASH: "Flash", IMAGE: "Image" };
  CompanionAdSelectionSettings.ResourceType = { ALL: "All", HTML: "Html", IFRAME: "IFrame", STATIC: "Static" };
  CompanionAdSelectionSettings.SizeCriteria = { IGNORE: "IgnoreSize", SELECT_EXACT_MATCH: "SelectExactMatch",
    SELECT_NEAR_MATCH: "SelectNearMatch", SELECT_FLUID: "SelectFluid" };

  var ima = {
    VERSION: "3.700.0", settings: settings,
    AdDisplayContainer: AdDisplayContainer, AdsLoader: AdsLoader, AdsManager: AdsManager, AdsRequest: AdsRequest,
    AdsRenderingSettings: AdsRenderingSettings, ImaSdkSettings: ImaSdkSettings,
    CompanionAdSelectionSettings: CompanionAdSelectionSettings, AdError: AdError, AdErrorEvent: AdErrorEvent,
    AdEvent: AdEvent, AdsManagerLoadedEvent: AdsManagerLoadedEvent,
    ViewMode: { NORMAL: "normal", FULLSCREEN: "fullscreen" },
    UiElements: { AD_ATTRIBUTION: "adAttribution", COUNTDOWN: "countdown" },
    OmidAccessMode: { LIMITED: "limited", DOMAIN: "domain", FULL: "full" },
    OmidVerificationVendor: { COMSCORE: 7, DOUBLEVERIFY: 3, GOOGLE: 9, INTEGRAL_AD_SCIENCE: 4, MEETRICS: 8,
      MOAT: 2, NIELSEN: 6, PIXELATE: 5, OTHER: 1 },
    AdsRequestOptions: {}
  };

  var ok = R.trap(win, "google.ima", {
    init: function (st) { st.cur = ima; return true; },
    get: function (st) { return st.cur; },
    set: function (st, v) { if (v !== undefined && v !== null && typeof v !== "object") st.cur = v; }
  });
  if (!ok) return;
  var g;
  try { g = win.google; } catch (e) { return; }
  if (!R.isObj(g)) { try { win.google = {}; } catch (e) { /* ignore */ } }
}
