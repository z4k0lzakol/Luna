// @world: main
// nofab (fuckadblock.js-3.2.0, prevent-fab-3.2.0): inert FuckAdBlock / BlockAdBlock / SniffAdBlock 3.2.0
// constructors + fuckAdBlock / blockAdBlock / sniffAdBlock instances that never detect anything and always call
// the "not detected" callbacks asynchronously. The six globals are set-constant-style accessors: a later write
// of the same type (the real library) is ignored, a write of another type wins. Spec 03c 14, 04 5.17.
function (R, ...args) {
  var win = R.win;
  var later = function (fn) { if (typeof fn === "function") R.later(fn, 1); };
  var FuckAdBlock = function FuckAdBlock(options) {
    this._options = { checkOnLoad: false, resetOnEnd: false, loopCheckTime: 50, loopMaxNumber: 5, baitClass: "", baitStyle: "" };
    this._var = { version: "3.2.0", bait: null, checking: false, loop: null, loopNumber: 0, event: { detected: [], notDetected: [] } };
    if (options !== undefined) this.setOption(options);
  };
  var p = FuckAdBlock.prototype;
  p.setOption = function (options, value) {
    if (value !== undefined) { var k = options; options = {}; options[k] = value; }
    if (options && typeof options === "object") {
      for (var o in options) { if (o in this._options) this._options[o] = options[o]; }
    }
    return this;
  };
  p.check = function (loop) {
    var l = this._var.event.notDetected;
    for (var i = 0; i < l.length; i++) later(l[i]);
    return true;
  };
  p.emitEvent = function (detected) {
    if (detected === false) {
      var l = this._var.event.notDetected;
      for (var i = 0; i < l.length; i++) later(l[i]);
    }
    if (this._options.resetOnEnd) this.clearEvent();
    return this;
  };
  p.clearEvent = function () { this._var.event.detected = []; this._var.event.notDetected = []; };
  p.on = function (detected, fn) {
    if (!detected && typeof fn === "function") { this._var.event.notDetected.push(fn); later(fn); }
    return this;
  };
  p.onDetected = function (fn) { return this; };
  p.onNotDetected = function (fn) { return this.on(false, fn); };
  var inst = new FuckAdBlock();
  function pin(name, value) {
    var cur = value;
    R.defineAccessor(win, name, function () { return cur; }, function (rcv, v) {
      if (v !== undefined && v !== null && typeof v !== typeof value) cur = v;
    }, true);
  }
  pin("FuckAdBlock", FuckAdBlock);
  pin("BlockAdBlock", FuckAdBlock);
  pin("SniffAdBlock", FuckAdBlock);
  pin("fuckAdBlock", inst);
  pin("blockAdBlock", inst);
  pin("sniffAdBlock", inst);
}
