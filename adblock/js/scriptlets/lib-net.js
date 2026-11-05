// @world: main
// lib-net: internal helper of SCRIPTLETS-1 (not a filter-list name; lists cannot invoke it).
// fetch / XHR / JSON plumbing shared by prevent-fetch, prevent-xhr, json-prune*, json-edit*, trusted-replace-*,
// xml-prune and m3u-prune (spec 02 12-13, 03b 1). One instance per realm (cached on R): ONE fetch wrapper, ONE set
// of XHR hooks, ONE JSON.parse / Response.prototype.json wrapper, whatever the number of scriptlets.
//   N.matcher(propsToMatch, emptyIsAll) -> fn(req) -> bool, or null ("" without emptyIsAll = log-only form)
//   N.directive(text, trusted) -> body spec      (03b 1.2)
//   N.config(text, trusted) -> response config | null when invalid
//   N.fake(fn(req, stack) -> {body, cfg, throttle, trusted} | null, where)      where: "fetch" | "xhr" | "both"
//   N.editResponse(ed, where)  ed = {test(req, stack) -> bool, kind: "text"|"json"|"jsonl"|"xml", run, doc?}
//       text: run(text) -> new text | null ; json / jsonl: run(obj) -> changed (in place) ;
//       xml: run(text) -> new text | null, doc(xmlDocument) -> changed (in place)
//   N.editRequest(ed, where)   same shape, applied to string request bodies (fetch init.body / Request, XHR send)
//   N.onJson(fn(obj, stack, text))   results of JSON.parse and Response.prototype.json (in place)
// req = {url (absolute), method (upper-case), prop(name)}; stack() = R.stack of the page call (lazy, sync only).
// Faked XHRs load from R.SR + "x/<b64url(JSON {t: mime, b: text} | {t: mime, n: length})>" or R.SR + "r/<resource>"
// (custom scheme: genuine events/status, no CSP connect-src); without a scheme from a data: URL.
function (R) {
  if (R.xnet) return R.xnet;
  var n = R.n, apply = R.apply, win = R.win, gOPD = n.getOwnPropertyDescriptor;
  var N = {};
  R.xnet = N;
  var WMp = n.WeakMap.prototype, wmGet = WMp.get, wmSet = WMp.set, wmDel = WMp["delete"];
  var create = n.create, JP = n.JSON_parse, JS = n.JSON_stringify, JSONo = win.JSON;
  var pThen = n.promiseThen, isObj = R.isObj;
  function G(proto, p) { try { var d = gOPD(proto, p); return d && d.get; } catch (e) { return undefined; } }
  function call(f, th, a) { return apply(f, th, a || []); }
  function then(p, ok, ko) { return apply(pThen, p, ko ? [ok, ko] : [ok]); }

  // ------------------------------------------------------------ natives (install time = document creation)
  var Resp = n.Response, RespP = Resp.prototype, Req = n.Request, ReqP = Req.prototype;
  var rClone = RespP.clone, rText = RespP.text, rBuf = RespP.arrayBuffer, rJson = RespP.json;
  var rg = { url: G(RespP, "url"), type: G(RespP, "type"), redirected: G(RespP, "redirected"),
             status: G(RespP, "status"), statusText: G(RespP, "statusText"), ok: G(RespP, "ok"),
             headers: G(RespP, "headers") };
  var qg = { url: G(ReqP, "url"), method: G(ReqP, "method"), mode: G(ReqP, "mode"), credentials: G(ReqP, "credentials"),
             cache: G(ReqP, "cache"), redirect: G(ReqP, "redirect"), referrer: G(ReqP, "referrer"),
             referrerPolicy: G(ReqP, "referrerPolicy"), integrity: G(ReqP, "integrity"),
             keepalive: G(ReqP, "keepalive"), headers: G(ReqP, "headers"), signal: G(ReqP, "signal"),
             body: G(ReqP, "body") };
  var qClone = ReqP.clone, qText = ReqP.text;
  var hGet = n.Headers.prototype.get, hForEach = n.Headers.prototype.forEach;
  var urlHref = G(n.URL.prototype, "href"), urlOrigin = G(n.URL.prototype, "origin");
  var baseURIGet = G(n.Node.prototype, "baseURI");
  var AS = win.AbortSignal, sigAborted = AS && G(AS.prototype, "aborted"), sigReason = AS && G(AS.prototype, "reason");
  var TE = n.TextEncoder, teEncode = TE && TE.prototype.encode;
  var U8 = win.Uint8Array, taSub = U8 && n.getPrototypeOf(U8.prototype).subarray;
  var taLen = U8 && G(n.getPrototypeOf(U8.prototype), "length");
  var bufLen = G(win.ArrayBuffer.prototype, "byteLength");
  var locOrigin = "";
  try { locOrigin = R.str(win.location.origin); } catch (e) { locOrigin = ""; }

  function absURL(raw) {
    var s = null;
    if (typeof raw === "string") s = raw;
    else if (isObj(raw)) {
      try { s = call(urlHref, raw); } catch (e) { s = null; }
      if (s === null) return null;
    } else if (raw === undefined || raw === null) return null;
    else s = R.str(raw);
    var base;
    try { base = call(baseURIGet, R.doc); } catch (e) { base = undefined; }
    try { return call(urlHref, new n.URL(s, base)); } catch (e) { return null; }
  }
  function originOf(u) { try { return call(urlOrigin, new n.URL(u)); } catch (e) { return ""; } }

  // ------------------------------------------------------------ request descriptor / matching (02 12)
  var PROPS = ["url", "method", "mode", "credentials", "cache", "redirect", "referrer", "referrerPolicy",
               "integrity", "keepalive", "priority", "body", "headers"];
  var DEF = { mode: "cors", credentials: "same-origin", cache: "default", redirect: "follow",
              referrer: "about:client", referrerPolicy: "", integrity: "", keepalive: "false", priority: "auto" };
  function mkReq(url, method, src) {
    var req = { url: url, method: method, c: create(null) };
    req.prop = function (k) {
      if (k === "url") return req.url;
      if (k === "method") return req.method;
      if (k in req.c) return req.c[k];
      var v = "";
      try { v = src ? src(k) : ""; } catch (e) { v = ""; }
      req.c[k] = v;
      return v;
    };
    return req;
  }
  function headersText(h) {
    var o = create(null), any = false;
    try {
      if (!isObj(h)) return "";
      var ok = false;
      try { call(hForEach, h, [function (v, k) { o[k] = v; any = true; }]); ok = true; } catch (e) { ok = false; }
      if (!ok) {
        if (n.isArray(h)) {
          for (var i = 0; i < h.length; i++) if (n.isArray(h[i])) { o[R.str(h[i][0])] = R.str(h[i][1]); any = true; }
        } else {
          var ks = n.keys(h);
          for (var j = 0; j < ks.length; j++) { o[ks[j]] = R.str(h[ks[j]]); any = true; }
        }
      }
    } catch (e) { return ""; }
    return any ? call(JS, JSONo, [o]) : "";
  }
  N.matcher = function (spec, emptyIsAll) {
    var s = R.trim(R.str(spec));
    if (s === "*" || (s === "" && emptyIsAll)) return function () { return true; };
    if (s === "") return null;
    var toks = R.split(s, /\s+/), tests = [];
    for (var i = 0; i < toks.length; i++) {
      var tk = toks[i];
      if (tk === "") continue;
      var c = R.indexOf(tk, ":"), k = "url", v = tk;
      if (c > 0 && tk.charAt(0) !== "/") {
        var nm = R.slice(tk, 0, c);
        if (apply(n.aIndexOf, PROPS, [nm]) !== -1) { k = nm; v = R.slice(tk, c + 1); }
      }
      R.push(tests, { k: k, P: R.pattern(v, true) });
    }
    return function (req) {
      for (var t = 0; t < tests.length; t++) if (!tests[t].P.test(req.prop(tests[t].k))) return false;
      return true;
    };
  };

  // ------------------------------------------------------------ body directives / response config (03b 1.2)
  var AN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  function rnd(len) {
    var out = [], i;
    for (i = 0; i < len; i++) {
      var k = call(n.Math_floor, win.Math, [call(n.Math_random, win.Math) * 62]);
      out[i] = AN.charAt(k);
    }
    return R.join(out, "");
  }
  N.random = rnd;
  var MIMES = { js: "application/javascript", json: "application/json", xml: "application/xml", txt: "text/plain",
                html: "text/html", css: "text/css", png: "image/png", gif: "image/gif", mp3: "audio/mpeg",
                mp4: "video/mp4", webm: "video/webm" };
  function mimeOf(name) {
    var m = apply(n.reExec, /\.([a-z0-9]+)$/i, [name]);
    var e = m ? R.lower(m[1]) : "";
    return MIMES[e] || "text/plain";
  }
  N.directive = function (raw, trusted) {
    var s = R.str(raw);
    if (s === "" || s === "emptyStr") return { text: "", mime: "text/plain" };
    if (s === "true") return { text: rnd(10), mime: "text/plain" };
    if (s === "emptyObj") return { text: "{}", mime: "application/json" };
    if (s === "emptyArr") return { text: "[]", mime: "application/json" };
    var m = apply(n.reExec, /^length:(\d+)(?:-(\d+))?$/, [s]);
    if (m) {
      var lo = n.Number(m[1]), hi = m[2] !== undefined ? n.Number(m[2]) : lo;
      if (hi < lo || hi > 500000) return { text: "", mime: "text/plain" };
      return { lo: lo, hi: hi, mime: "text/plain" };
    }
    if (R.startsWith(s, "war:")) {
      var nm = R.slice(s, 4);
      if (apply(n.reTest, /^[\w.+-]+$/, [nm])) return { war: nm, mime: mimeOf(nm) };
      return { text: "", mime: "text/plain" };
    }
    return { text: trusted ? s : "", mime: "text/plain" };
  };
  function bodyText(b) {   // materialise a text directive (random lengths are drawn per request)
    if (b.lo !== undefined) {
      var len = b.lo + call(n.Math_floor, win.Math, [call(n.Math_random, win.Math) * (b.hi - b.lo + 1)]);
      return rnd(len);
    }
    return b.text || "";
  }
  var TYPES = ["basic", "cors", "default", "error", "opaque", "opaqueredirect"];
  N.config = function (raw, trusted) {
    var s = R.trim(R.str(raw)), cfg = create(null), o;
    if (s === "") return cfg;
    if (apply(n.aIndexOf, TYPES, [s]) !== -1) { cfg.type = s; return cfg; }
    try { o = call(JP, JSONo, [s]); } catch (e) { return null; }
    if (!isObj(o) || n.isArray(o)) return null;
    if (typeof o.ok === "boolean") cfg.ok = o.ok;
    if (typeof o.type === "string" && apply(n.aIndexOf, TYPES, [o.type]) !== -1) cfg.type = o.type;
    if (typeof o.statusText === "string" && (trusted || o.statusText === "" || o.statusText === "OK" ||
        o.statusText === "Not Found")) cfg.statusText = o.statusText;
    if (typeof o.status === "number" && o.status >= 0 && o.status <= 599 && call(n.Math_floor, win.Math, [o.status]) === o.status) cfg.status = o.status;
    if (typeof o.redirected === "boolean") cfg.redirected = o.redirected;
    if (trusted && isObj(o.headers) && !n.isArray(o.headers)) {
      var hs = create(null), ks = n.keys(o.headers);
      for (var i = 0; i < ks.length; i++) if (typeof o.headers[ks[i]] === "string") hs[R.lower(ks[i])] = o.headers[ks[i]];
      cfg.headers = hs;
    }
    return cfg;
  };

  // ------------------------------------------------------------ registries
  var F = { fakes: [], resp: [], req: [] }, X = { fakes: [], resp: [], req: [] }, JH = [];
  function reg(where, key, v) {
    if (where !== "xhr") { R.push(F[key], v); setupFetch(); }
    if (where !== "fetch") { R.push(X[key], v); setupXhr(); }
  }
  N.fake = function (fn, where) { reg(where || "both", "fakes", fn); };
  N.editResponse = function (ed, where) { reg(where || "both", "resp", ed); };
  N.editRequest = function (ed, where) { reg(where || "both", "req", ed); };
  function pick(list, req, stk) {
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var hit = false;
      try { hit = list[i].test(req, stk) === true; } catch (e) { hit = false; }
      if (hit) R.push(out, list[i]);
    }
    return out;
  }
  function stackOf(fn) {
    var s = null;
    return function () { if (s === null) s = R.stack(fn); return s; };
  }

  // ------------------------------------------------------------ editing helpers
  function parseJ(t) { return call(JP, JSONo, [t]); }
  function strJ(v) { return call(JS, JSONo, [v]); }
  function runOnText(ed, text) {
    if (typeof text !== "string") return null;
    var r = null;
    try {
      if (ed.kind === "text" || ed.kind === "xml") {
        r = ed.run(text);
        return typeof r === "string" && r !== text ? r : null;
      }
      if (ed.kind === "json") {
        var o;
        try { o = parseJ(text); } catch (e) { return null; }
        if (!isObj(o)) return null;
        return ed.run(o) ? strJ(o) : null;
      }
      if (ed.kind === "jsonl") {
        var lines = R.split(text, "\n"), ch = false;
        for (var i = 0; i < lines.length; i++) {
          var ln = lines[i], cr = R.endsWith(ln, "\r");
          var body = cr ? R.slice(ln, 0, ln.length - 1) : ln;
          if (R.trim(body) === "") continue;
          var lo;
          try { lo = parseJ(body); } catch (e) { continue; }
          if (isObj(lo) && ed.run(lo)) { lines[i] = strJ(lo) + (cr ? "\r" : ""); ch = true; }
        }
        return ch ? R.join(lines, "\n") : null;
      }
    } catch (e) { return null; }
    return null;
  }
  function editText(text, eds) {
    var cur = text, ch = false;
    for (var i = 0; i < eds.length; i++) {
      var r = runOnText(eds[i], cur);
      if (r !== null) { cur = r; ch = true; }
    }
    return ch ? cur : null;
  }
  N.editText = editText;

  // ------------------------------------------------------------ Response masking (02 13.1/13.3)
  var masks = new n.WeakMap(), maskOn = false;
  function setMask(r, m) { apply(wmSet, masks, [r, m]); }
  function getMask(r) { return isObj(r) ? apply(wmGet, masks, [r]) : undefined; }
  function rget(r, k) {
    var m = getMask(r);
    if (m && k in m) return m[k];
    return call(rg[k], r);
  }
  function setupMasks() {
    if (maskOn) return;
    maskOn = true;
    var keys = ["url", "type", "redirected", "status", "statusText", "ok"];
    for (var i = 0; i < keys.length; i++) {
      (function (k) {
        R.wrapAccessor(RespP, k, { get: function (t, th, a) {
          var m = getMask(th);
          if (m && k in m) return m[k];
          return apply(t, th, a);
        } });
      })(keys[i]);
    }
    R.wrapMethod(RespP, "clone", function (t, th, a) {
      var c = apply(t, th, a), m = getMask(th);
      if (m) {
        var m2 = create(null), ks = n.keys(m);
        for (var j = 0; j < ks.length; j++) m2[ks[j]] = m[ks[j]];
        setMask(c, m2);
      }
      return c;
    });
  }

  // ------------------------------------------------------------ fetch
  var fetchOn = false;
  function fetchReq(a) {
    var res = a[0], init = a.length > 1 ? a[1] : undefined, isReq = false, url = null;
    if (isObj(res)) {
      try { url = call(qg.url, res); isReq = true; } catch (e) { url = null; }
    }
    if (!isReq) url = absURL(res);
    if (url === null) return null;
    var hasInit = isObj(init);
    function fromInit(k) {
      if (!hasInit) return undefined;
      try { if (!(k in init)) return undefined; return init[k]; } catch (e) { return undefined; }
    }
    var mi = fromInit("method"), method;
    if (mi !== undefined) method = R.str(mi);
    else if (isReq) { try { method = call(qg.method, res); } catch (e) { method = "GET"; } }
    else method = "GET";
    method = apply(n.sToUpperCase, method, []);
    var req = mkReq(url, method, function (k) {
      var v = fromInit(k);
      if (k === "body") return typeof v === "string" ? v : "";
      if (k === "headers") {
        if (v !== undefined) return headersText(v);
        return isReq ? headersText(call(qg.headers, res)) : "";
      }
      if (v !== undefined) return R.str(v);
      if (isReq && qg[k]) return R.str(call(qg[k], res));
      return DEF[k] !== undefined ? DEF[k] : "";
    });
    req.isReq = isReq;
    req.signal = function () {
      var sg = fromInit("signal");
      if (sg === undefined && isReq) { try { sg = call(qg.signal, res); } catch (e) { sg = undefined; } }
      return isObj(sg) ? sg : null;
    };
    return req;
  }
  function aborted(sg) { try { return !!sg && call(sigAborted, sg) === true; } catch (e) { return false; } }
  function reasonOf(sg) { try { return call(sigReason, sg); } catch (e) { return undefined; } }
  function byteLength(text) {
    try { return call(taLen, call(teEncode, new TE(), [text])); } catch (e) { return text.length; }
  }
  function buildResponse(req, spec, body, mime) {
    var cfg = spec.cfg || create(null);
    var type = cfg.type;
    if (type === undefined) {
      var o = originOf(req.url);
      if (o === locOrigin || R.startsWith(req.url, "data:") || R.startsWith(req.url, "blob:")) type = "basic";
      else type = req.prop("mode") === "no-cors" ? "opaque" : "cors";
    }
    if (type === "error") return call(Resp.error, Resp);
    var m = create(null);
    m.url = req.url; m.type = type; m.redirected = cfg.redirected === true;
    var hd = {}, init = { status: 200, statusText: "OK", headers: hd };
    if (type === "opaque" || type === "opaqueredirect") {
      m.status = 0; m.statusText = ""; m.ok = false; m.url = "";
      body = null;
    } else {
      hd["content-type"] = mime;
      if (cfg.status !== undefined) {
        if (cfg.status >= 200) init.status = cfg.status;
        else m.status = cfg.status;
        m.ok = cfg.status >= 200 && cfg.status <= 299;
      }
      if (cfg.statusText !== undefined) init.statusText = cfg.statusText;
      if (cfg.ok !== undefined) m.ok = cfg.ok;
      if (cfg.headers) { var ks = n.keys(cfg.headers); for (var i = 0; i < ks.length; i++) hd[ks[i]] = cfg.headers[ks[i]]; }
      var st = init.status;
      if (req.method === "HEAD" || st === 101 || st === 103 || st === 204 || st === 205 || st === 304) {
        if (body !== null) hd["content-length"] = R.str(typeof body === "string" ? byteLength(body) : call(bufLen, body));
        body = null;
      } else if (body !== null && hd["content-length"] === undefined) {
        hd["content-length"] = R.str(typeof body === "string" ? byteLength(body) : call(bufLen, body));
      }
    }
    var r;
    try { r = new Resp(body, init); }
    catch (e) { init.statusText = "OK"; if (init.status < 200 || init.status > 599) init.status = 200; r = new Resp(body, init); }
    setMask(r, m);
    return r;
  }
  function fakeFetch(req, spec) {
    return new n.Promise(function (resolve, reject) {
      var sg = req.signal();
      if (aborted(sg)) { reject(reasonOf(sg)); return; }
      var go = function () {
        if (aborted(sg)) { reject(reasonOf(sg)); return; }
        var b = spec.body;
        if (b.war !== undefined && R.SR !== "") {
          var p;
          try {
            p = call(n.fetch, win, [R.SR + "r/" + call(n.encodeURIComponent, win, [b.war]), { credentials: "omit" }]);
          } catch (e) { p = null; }
          if (!p) { resolve(buildResponse(req, spec, "", b.mime)); return; }
          var q = then(p, function (rs) {
            var ct = b.mime;
            try { ct = call(hGet, call(rg.headers, rs), ["content-type"]) || b.mime; } catch (e) { ct = b.mime; }
            return then(call(rBuf, rs), function (buf) {
              if (aborted(sg)) { reject(reasonOf(sg)); return; }
              resolve(buildResponse(req, spec, buf, ct));
            });
          });
          then(q, null, function () { resolve(buildResponse(req, spec, "", b.mime)); });
          return;
        }
        resolve(buildResponse(req, spec, b.war !== undefined ? "" : bodyText(b), b.mime));
      };
      R.later(go, spec.throttle > 0 ? spec.throttle : 0);
    });
  }
  function editFetchResponse(resp, eds) {
    var type, status;
    try { type = rget(resp, "type"); status = rget(resp, "status"); } catch (e) { return resp; }
    if (type === "opaque" || type === "opaqueredirect" || type === "error" || status < 200 || status > 299) return resp;
    var c;
    try { c = call(rClone, resp); } catch (e) { return resp; }
    return then(call(rText, c), function (text) {
      var out = editText(text, eds);
      if (out === null) return resp;
      var nr;
      try {
        nr = new Resp(out, { status: call(rg.status, resp), statusText: call(rg.statusText, resp),
                             headers: call(rg.headers, resp) });
      } catch (e) { return resp; }
      var m = create(null), om = getMask(resp), ks, i;
      if (om) { ks = n.keys(om); for (i = 0; i < ks.length; i++) m[ks[i]] = om[ks[i]]; }
      m.url = rget(resp, "url"); m.type = type; m.redirected = rget(resp, "redirected");
      setMask(nr, m);
      return nr;
    }, function () { return resp; });
  }
  function editFetchRequest(t, th, a, eds) {
    var init = a.length > 1 ? a[1] : undefined, res = a[0], b;
    if (isObj(init)) {
      var body;
      try { body = ("body" in init) ? init.body : undefined; } catch (e) { body = undefined; }
      if (typeof body === "string") {
        var out = editText(body, eds);
        if (out === null) return apply(t, th, a);
        var ni = call(n.assign, null, [{}, init]);
        ni.body = out;
        b = R.slice(a, 0);
        b[1] = ni;
        return apply(t, th, b);
      }
      if (body !== undefined) return apply(t, th, a);
    }
    var rb = null;
    try { rb = call(qg.body, res); } catch (e) { rb = null; }
    if (!rb) return apply(t, th, a);
    var c;
    try { c = call(qClone, res); } catch (e) { return apply(t, th, a); }
    return then(call(qText, c), function (text) {
      var out2 = editText(text, eds);
      if (out2 === null) return apply(t, th, a);
      var nr = new Req(res, { body: out2 });
      var b2 = R.slice(a, 0);
      b2[0] = nr;
      return apply(t, th, b2);
    }, function () { return apply(t, th, a); });
  }
  function fetchHook(t, th, a) {
    if (th !== undefined && th !== null && th !== win) return apply(t, th, a);
    if (!F.fakes.length && !F.resp.length && !F.req.length) return apply(t, th, a);
    var req = null;
    try { req = fetchReq(a); } catch (e) { req = null; }
    if (!req) return apply(t, th, a);
    var stk = stackOf(fetchHook), i;
    for (i = 0; i < F.fakes.length; i++) {
      var spec = null;
      try { spec = F.fakes[i](req, stk); } catch (e) { spec = null; }
      if (spec) return fakeFetch(req, spec);
    }
    var eds = pick(F.resp, req, stk), reqEds = pick(F.req, req, stk);
    var p = reqEds.length ? editFetchRequest(t, th, a, reqEds) : apply(t, th, a);
    if (!eds.length) return p;
    return then(p, function (resp) { return editFetchResponse(resp, eds); });
  }
  function setupFetch() {
    if (fetchOn) return;
    fetchOn = true;
    setupMasks();
    R.wrapMethod(win, "fetch", fetchHook);
  }

  // ------------------------------------------------------------ XHR (02 13.2 / 13.4)
  var XHR = n.XMLHttpRequest, XP = XHR && XHR.prototype, xhrOn = false;
  var xg = XP ? { readyState: G(XP, "readyState"), responseType: G(XP, "responseType"), response: G(XP, "response"),
                  responseText: G(XP, "responseText"), responseXML: G(XP, "responseXML") } : null;
  var xrec = new n.WeakMap();
  var DPp = n.DOMParser && n.DOMParser.prototype, dpParse = DPp && DPp.parseFromString;
  function utf8b64(s, url) {
    var bytes = call(teEncode, new TE(), [s]), len = call(taLen, bytes), out = "";
    for (var i = 0; i < len; i += 4096) {
      out += apply(n.fromCharCode, null, call(taSub, bytes, [i, i + 4096 < len ? i + 4096 : len]));
    }
    out = call(n.btoa, win, [out]);
    if (url) out = R.sreplace(R.sreplace(R.sreplace(out, /\+/g, "-"), /\//g, "_"), /=+$/, "");
    return out;
  }
  function fakeURL(spec) {
    var b = spec.body;
    if (R.SR !== "") {
      if (b.war !== undefined) return R.SR + "r/" + call(n.encodeURIComponent, win, [b.war]);
      var o = { t: b.mime };
      if (b.lo !== undefined) o.n = b.lo + call(n.Math_floor, win.Math, [call(n.Math_random, win.Math) * (b.hi - b.lo + 1)]);
      else o.b = b.text || "";
      return R.SR + "x/" + utf8b64(strJ(o), true);
    }
    return "data:" + b.mime + ";base64," + utf8b64(b.war !== undefined ? "" : bodyText(b), false);
  }
  function openHook(t, th, a) {
    try { call(xg.readyState, th); } catch (e) { return apply(t, th, a); }
    apply(wmDel, xrec, [th]);
    if (a.length < 2 || typeof a[0] !== "string") return apply(t, th, a);
    var url = absURL(a[1]);
    if (url === null) return apply(t, th, a);
    var req = mkReq(url, apply(n.sToUpperCase, a[0], []), null);
    var stk = stackOf(openHook), i;
    var rec = { url: url, fake: null, eds: [], reqEds: [], cache: null };
    for (i = 0; i < X.fakes.length; i++) {
      var spec = null;
      try { spec = X.fakes[i](req, stk); } catch (e) { spec = null; }
      if (spec) {
        var fu;
        try { fu = fakeURL(spec); } catch (e) { fu = null; }
        if (fu === null) break;
        rec.fake = spec;
        apply(wmSet, xrec, [th, rec]);
        return apply(t, th, [a[0], fu, a.length > 2 ? !!a[2] : true]);
      }
    }
    rec.eds = pick(X.resp, req, stk);
    rec.reqEds = pick(X.req, req, stk);
    if (rec.eds.length || rec.reqEds.length) apply(wmSet, xrec, [th, rec]);
    return apply(t, th, a);
  }
  function sendHook(t, th, a) {
    var rec = isObj(th) ? apply(wmGet, xrec, [th]) : undefined;
    if (rec && rec.reqEds.length && typeof a[0] === "string") {
      var out = editText(a[0], rec.reqEds);
      if (out !== null) { var b = R.slice(a, 0); b[0] = out; return apply(t, th, b); }
    }
    return apply(t, th, a);
  }
  var xOpenN = XP && XP.open, xSendN = XP && XP.send;
  // XML text -> XMLDocument | null. DOMParser.parseFromString is a Trusted Types sink (a violation report on TT
  // pages), so the text is parsed by a synchronous XHR to the CSP-ignored scheme (responseXML is not a sink).
  function xmlDoc(text) {
    if (R.SR !== "" && XP) {
      try {
        var x = new XHR();
        call(xOpenN, x, ["GET", R.SR + "x/" + utf8b64(strJ({ t: "application/xml", b: text }), true), false]);
        call(xSendN, x, []);
        var d0 = call(xg.responseXML, x);
        if (!d0 || call(n.querySelector, d0, ["parsererror"])) return null;
        return d0;
      } catch (e) { /* no scheme / sync XHR disabled: DOMParser below */ }
    }
    try {
      var d = call(dpParse, new n.DOMParser(), [text, "text/xml"]);
      if (call(n.querySelector, d, ["parsererror"])) return null;
      return d;
    } catch (e) { return null; }
  }
  function xhrEdited(th, rec) {
    if (rec.cache) return rec.cache;
    var c = { t: null, o: undefined, doc: undefined, rt: "" };
    rec.cache = c;
    var rt = "";
    try { rt = call(xg.responseType, th); } catch (e) { return c; }
    c.rt = rt;
    var eds = rec.eds, i;
    if (rt === "" || rt === "text") {
      var text;
      try { text = call(xg.responseText, th); } catch (e) { return c; }
      c.t = editText(text, eds);
    } else if (rt === "json") {
      var obj;
      try { obj = call(xg.response, th); } catch (e) { return c; }
      if (!isObj(obj)) return c;
      var ch = false;
      for (i = 0; i < eds.length; i++) {
        try {
          if (eds[i].kind === "json") { if (eds[i].run(obj)) ch = true; }
          else if (eds[i].kind === "text") {
            var s0 = strJ(obj), s1 = eds[i].run(s0);
            if (typeof s1 === "string" && s1 !== s0) { obj = parseJ(s1); ch = true; }
          }
        } catch (e) { /* keep */ }
      }
      if (ch) c.o = obj;
    } else if (rt === "document") {
      var dd;
      try { dd = call(xg.response, th); } catch (e) { return c; }
      if (dd) for (i = 0; i < eds.length; i++) { if (eds[i].kind === "xml" && eds[i].doc) { try { eds[i].doc(dd); } catch (e) { /* ignore */ } } }
    }
    return c;
  }
  function done(th) { try { return call(xg.readyState, th) === 4; } catch (e) { return false; } }
  function setupXhr() {
    if (xhrOn || !XP) return;
    xhrOn = true;
    R.wrapMethod(XP, "open", openHook);
    R.wrapMethod(XP, "send", sendHook);
    R.wrapAccessor(XP, "responseURL", { get: function (t, th, a) {
      var v = apply(t, th, a), rec = isObj(th) ? apply(wmGet, xrec, [th]) : undefined;
      return rec && rec.fake && v !== "" ? rec.url : v;
    } });
    var edGet = function (which) {
      return function (t, th, a) {
        var v = apply(t, th, a), rec = isObj(th) ? apply(wmGet, xrec, [th]) : undefined;
        if (!rec || !rec.eds.length || !done(th)) return v;
        var c = xhrEdited(th, rec);
        if (which === "response") {
          if ((c.rt === "" || c.rt === "text") && c.t !== null) return c.t;
          if (c.rt === "json" && c.o !== undefined) return c.o;
          return v;
        }
        if (which === "responseText") return c.t !== null ? c.t : v;
        if (c.t !== null && v) {   // responseXML of an edited text response
          if (c.doc === undefined) c.doc = xmlDoc(c.t);
          return c.doc || v;
        }
        return v;
      };
    };
    R.wrapAccessor(XP, "response", { get: edGet("response") });
    R.wrapAccessor(XP, "responseText", { get: edGet("responseText") });
    R.wrapAccessor(XP, "responseXML", { get: edGet("responseXML") });
    var RE_AC = /^access-control-[^\r\n]*\r?\n?/gim;
    R.wrapMethod(XP, "getAllResponseHeaders", function (t, th, a) {
      var v = apply(t, th, a), rec = isObj(th) ? apply(wmGet, xrec, [th]) : undefined;
      if (rec && rec.fake && typeof v === "string") { RE_AC.lastIndex = 0; v = R.sreplace(v, RE_AC, ""); }
      return v;
    });
    R.wrapMethod(XP, "getResponseHeader", function (t, th, a) {
      var v = apply(t, th, a), rec = isObj(th) ? apply(wmGet, xrec, [th]) : undefined;
      if (rec && rec.fake && typeof a[0] === "string" && R.startsWith(R.lower(a[0]), "access-control-")) return null;
      return v;
    });
  }

  // ------------------------------------------------------------ JSON.parse / Response.prototype.json
  var jsonOn = false;
  N.onJson = function (fn) {
    R.push(JH, fn);
    if (jsonOn) return;
    jsonOn = true;
    var jpHook = function (t, th, a) {
      var r = apply(t, th, a);
      if (isObj(r) && JH.length) {
        var stk = stackOf(jpHook), text = typeof a[0] === "string" ? a[0] : null;
        for (var i = 0; i < JH.length; i++) { try { JH[i](r, stk, text); } catch (e) { /* ignore */ } }
      }
      return r;
    };
    R.wrapMethod(JSONo, "parse", jpHook);
    var rjHook = function (t, th, a) {
      var p = apply(t, th, a);
      if (!JH.length) return p;
      var s = R.stack(rjHook);
      return then(p, function (r) {
        if (isObj(r)) {
          for (var i = 0; i < JH.length; i++) { try { JH[i](r, function () { return s; }, null); } catch (e) { /* ignore */ } }
        }
        return r;
      });
    };
    R.wrapMethod(RespP, "json", rjHook);
  };
  N.parse = parseJ;
  N.stringify = strJ;
  N.xmlDoc = xmlDoc;
  return N;
}
