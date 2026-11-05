// Luna cosmetic engine. Runs in isolated world 7 (invisible to page JS), DocumentCreation, all frames.
// This file is ONE function expression; cosmetic.py wraps it as (ENGINE)(CFG).
// CFG = {sr: scheme base url, high: [generic selectors], gen_unhide: [selectors], allow: [base domains]}
// Per-host data arrives via __lc(data) / __lcq (see cosmetic.host_script). Contract: DESIGN §6, PROC_AST.md.
// Stealth: no DOM attributes/classes/<style>, no console, no page-visible globals. One adopted CSSStyleSheet.
function (CFG) {
  "use strict";
  var G = globalThis;
  if (G.__lce) return;
  G.__lce = 1;
  CFG = CFG || {};
  var D = document, W = window;
  var HIDE = "{display:none!important}";
  // generic hiding: off-screen so bait checks (offsetHeight, display, visibility) still pass
  var OFF = "{position:absolute!important;left:-10000px!important;top:-10000px!important}";
  var SR = typeof CFG.sr === "string" ? CFG.sr : "";
  var perf = W.performance;
  var now = function () { return perf.now(); };
  var ST = G.__lcstat = {cb: 0, ms: 0, survMs: 0, passes: 0, passMs: 0, fetches: 0, tokens: 0, lowly: 0, rebuilds: 0, readds: 0};
  var arr = function (v) { return Array.isArray(v) ? v : []; };
  var str = function (v) { return typeof v === "string" && v.length > 0; };

  // ------------------------------------------------------------------ allowlist (top-level base domain)
  function hostIn(h, list) {
    list = arr(list);
    for (var i = 0; i < list.length; i++) {
      var d = list[i];
      if (!str(d)) continue;
      if (h === d || (h.length > d.length && h.slice(-d.length - 1) === "." + d)) return true;
    }
    return false;
  }
  function topHost() {
    try { if (W.top === W) return location.hostname; } catch (e) {}
    try {
      var ao = location.ancestorOrigins;
      if (ao && ao.length) return new URL(ao[ao.length - 1]).hostname;
    } catch (e) {}
    return location.hostname;
  }
  // only web pages: never Luna's own pages (block page / click2load on our scheme, internal schemes) – a generic
  // rule like a[href^="https://ad.doubleclick.net/"] would otherwise hide the block page's "proceed" link
  var proto = String(location.protocol || "");
  if ((proto !== "http:" && proto !== "https:" && proto !== "about:") || hostIn(String(topHost() || "").toLowerCase(), CFG.allow)) {
    G.__lc = function () {};
    G.__lcq = undefined;
    return;
  }

  // ------------------------------------------------------------------ state
  var data = null, flags = 0, genOn = false, specOn = false, survey = true;
  var genUnhide = new Set(arr(CFG.gen_unhide)), hostUnhide = new Set();
  var high = arr(CFG.high);
  var sheet = null, expLen = 0, procCount = 0;
  var baseRules = [], lowRules = [], procRules = [];
  var lowAll = [], lowSeen = new Set();
  var removeSel = "";
  var procs = [];
  var hideT = [], styleT = [];          // last procedural targets (elements), re-verified on every mutation
  var seen = new Set(), sent = new Set(), pend = [], scanned = false;
  var watchMO = null, navHooked = false;
  var mqCache = new Map();

  function valid(sel) {
    try { D.createDocumentFragment().querySelector(sel); return true; } catch (e) { return false; }
  }
  var BAD_DECL = /[{}\\]|url\s*\(|image-set|@import|expression|\/\*|\/\s*\//i;
  function okDecl(d) { return str(d) && !BAD_DECL.test(d); }

  // ------------------------------------------------------------------ stylesheet
  function ensure() {
    if (!sheet) return;
    try {
      if (sheet.cssRules.length !== expLen) { rebuild(); return; }
      var a = D.adoptedStyleSheets;
      for (var i = a.length - 1; i >= 0; i--) if (a[i] === sheet) { if (!expLen) detach(); return; }
      if (!expLen) return;
      ST.readds++;
      try { a.push(sheet); } catch (e) { D.adoptedStyleSheets = Array.prototype.slice.call(a).concat([sheet]); }
    } catch (e) {}
  }
  function detach() {
    try {
      var a = D.adoptedStyleSheets;
      for (var i = a.length - 1; i >= 0; i--) if (a[i] === sheet) a.splice(i, 1);
    } catch (e) {}
  }
  function rebuild() {
    ST.rebuilds++;
    var total = baseRules.length + lowRules.length + procRules.length;
    if (!sheet) {
      if (!total) return;
      sheet = new CSSStyleSheet();
    }
    try { sheet.replaceSync(baseRules.concat(lowRules).join("\n")); } catch (e) { expLen = 0; return; }
    procCount = 0;
    for (var i = 0; i < procRules.length; i++) {
      try { sheet.insertRule(procRules[i], procCount); procCount++; } catch (e) {}
    }
    expLen = sheet.cssRules.length;
    ensure();
  }
  function addLowly(list) {
    var fresh = [];
    for (var i = 0; i < list.length; i++) {
      var s = list[i];
      if (!str(s) || lowSeen.has(s) || s.indexOf("{") >= 0 || s.indexOf("}") >= 0) continue;
      lowSeen.add(s);
      lowAll.push(s);
      if (genOn && !genUnhide.has(s) && !hostUnhide.has(s)) fresh.push(s + OFF);
    }
    if (!fresh.length) return;
    if (!sheet) { sheet = new CSSStyleSheet(); expLen = 0; }
    else if (sheet.cssRules.length !== expLen) rebuild();
    for (var j = 0; j < fresh.length; j++) {
      try { sheet.insertRule(fresh[j], sheet.cssRules.length); expLen++; lowRules.push(fresh[j]); ST.lowly++; } catch (e) {}
    }
    ensure();
  }

  // ------------------------------------------------------------------ surveyor (generic lowly selectors)
  var WS = /\s/;
  function addTok(t) {
    if (t.length < 256 && !seen.has(t)) { seen.add(t); if (survey) pend.push(t); }
  }
  function tok(el) {
    var id = el.id;
    if (typeof id === "string" && id && !WS.test(id)) addTok("#" + id);
    var cl = el.classList;
    if (cl) for (var j = 0; j < cl.length; j++) addTok("." + cl[j]);
  }
  function collect(n) {
    tok(n);
    if (n.firstElementChild) {
      var l = n.querySelectorAll("[id],[class]");
      for (var i = 0; i < l.length; i++) tok(l[i]);
    }
  }
  function fullScan() {
    if (!D.documentElement) return;
    scanned = true;
    collect(D.documentElement);
  }
  var inflight = false, lastFetch = -1e9, ftimer = 0;
  function flushTokens() {
    if (!genOn || !SR || !pend.length || inflight || ftimer) return;
    var wait = lastFetch + 50 - now();
    if (wait > 0) {
      ftimer = setTimeout(function () { ftimer = 0; flushTokens(); }, wait);
      return;
    }
    lastFetch = now();
    var len = 0, k = 0;
    while (k < pend.length && len < 6000) { len += pend[k].length + 1; k++; }
    var batch = pend.splice(0, k);
    batch.forEach(function (t) { sent.add(t); });
    inflight = true;
    ST.fetches++;
    ST.tokens += batch.length;
    var done = function () { inflight = false; if (pend.length) flushTokens(); };
    try {
      fetch(SR + "c?t=" + encodeURIComponent(batch.join(" ")), {credentials: "omit", cache: "no-store"})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (list) {
          try { if (Array.isArray(list)) addLowly(list); } catch (e) {}
          done();
        }, done);
    } catch (e) { done(); }
  }

  // ------------------------------------------------------------------ procedural compile (PROC_AST.md)
  function pat(x) {
    if (!x || typeof x !== "object") throw 1;
    if (typeof x.t === "string") {
      var t = x.t;
      return {test: function (s) { return String(s).indexOf(t) !== -1; }};
    }
    if (typeof x.r === "string") return new RegExp(x.r, String(x.f || "").replace(/[^imsu]/g, ""));
    throw 1;
  }
  function mq(q) {
    var m = mqCache.get(q);
    if (!m) {
      m = W.matchMedia(q);
      mqCache.set(q, m);
      try { m.addEventListener("change", function () { schedule(true); }); } catch (e) {}
    }
    return m;
  }
  // returns compiled chain; info collects watch needs
  function cchain(t, info, sub) {
    if (!Array.isArray(t) || !t.length) throw 1;
    var out = [];
    for (var i = 0; i < t.length; i++) {
      var s = t[i], op = s[0], a = s[1], c = {op: op};
      switch (op) {
        case "css":
          if (!str(a)) throw 1;
          c.s = a.trim();
          var lead = c.s.charAt(0);
          c.rel = sub && i === 0 && (lead === ">" || lead === "+" || lead === "~") ? lead : "";
          if (!valid(c.rel ? ":scope " + c.s : c.s)) throw 1;
          break;
        case "spath":
          if (!str(a)) throw 1;
          var f = a.trim(), ch = f.charAt(0);
          c.comb = (ch === ">" || ch === "+" || ch === "~") ? ch : " ";
          c.rest = c.comb === " " ? f : f.slice(1).trim();
          if (!c.rest || !valid(":scope " + c.comb + " " + c.rest)) throw 1;
          break;
        case "matches":
          if (!str(a) || !valid(a)) throw 1;
          c.s = a;
          break;
        case "has":
        case "not":
          c.sub = cchain(a, info, true);
          break;
        case "has-text":
        case "matches-path":
          c.p = pat(a);
          if (op === "matches-path") info.path = true;
          break;
        case "min-text-length":
          c.n = +a;
          if (!(c.n >= 0)) throw 1;
          break;
        case "matches-attr":
          c.np = pat(a);
          c.vp = s[2] ? pat(s[2]) : null;
          break;
        case "matches-css":
          c.pseudo = a ? "::" + String(a).replace(/^:+/, "") : null;
          if (!str(s[2])) throw 1;
          c.prop = s[2];
          c.p = pat(s[3]);
          break;
        case "matches-media":
          if (!str(a)) throw 1;
          c.m = mq(a);
          break;
        case "matches-prop":
          if (!str(a)) throw 1;
          c.chain = a.split(".");
          c.p = s[2] ? pat(s[2]) : null;
          break;
        case "others":
          break;
        case "upward":
          if (typeof a === "number") {
            c.n = a | 0;
            if (c.n < 1 || c.n > 255) throw 1;
          } else {
            if (!str(a) || !valid(a)) throw 1;
            c.s = a;
          }
          break;
        case "watch-attr":
          var names = arr(a).filter(str);
          if (!names.length) info.any = true;
          else names.forEach(function (n) { info.attrs.add(n); });
          break;
        case "xpath":
          if (!str(a)) throw 1;
          D.createExpression(a, null);
          c.x = a;
          break;
        default:
          throw 1;
      }
      out.push(c);
    }
    return out;
  }
  var EXACT = /^\^([\w:.-]+)\$$/;
  function cproc(p, info) {
    if (!p || typeof p !== "object") throw 1;
    var r = {s: p.s, t: cchain(p.t, info, false), a: null};
    var a = p.a;
    if (Array.isArray(a) && a.length) {
      var k = a[0];
      if (k === "style") {
        if (!okDecl(a[1])) throw 1;
        r.a = {k: k, decl: a[1]};
      } else if (k === "remove") {
        r.a = {k: k};
      } else if (k === "remove-attr" || k === "remove-class") {
        r.a = {k: k, p: pat(a[1])};
        if (k === "remove-class") info.attrs.add("class");
        else {
          var m = typeof a[1].r === "string" && EXACT.exec(a[1].r);
          if (m) info.attrs.add(m[1]); else info.any = true;
        }
      } else throw 1;
    }
    return r;
  }

  // ------------------------------------------------------------------ procedural evaluation
  var idxCache = null;     // Map(parent -> Map(child -> index)) during one procRuleTexts() call
  function idx(e) {
    var p = e.parentElement;
    if (idxCache && p && p.childElementCount > 32) {
      var m = idxCache.get(p);
      if (!m) {
        idxCache.set(p, m = new Map());
        var k = 1;
        for (var c = p.firstElementChild; c; c = c.nextElementSibling) m.set(c, k++);
      }
      return m.get(e) || 0;
    }
    var i = 1;
    while ((e = e.previousElementSibling)) i++;
    return i;
  }
  function uniq(set) { return Array.from(set); }
  function qsaInto(root, sel, out) {
    var l = root.querySelectorAll(sel);
    for (var i = 0; i < l.length; i++) out.add(l[i]);
  }
  function rel(e, comb, rest, out) {
    if (comb === " " || comb === ">") {
      qsaInto(e, ":scope " + comb + " " + rest, out);
    } else {
      var p = e.parentElement;
      if (p) qsaInto(p, ":scope > :nth-child(" + idx(e) + ") " + comb + " " + rest, out);
    }
  }
  function textOf(e) { return e.textContent || ""; }
  function others(set) {
    var marked = new Set(), inputs = new Set(set), out = [];
    for (var i = 0; i < set.length; i++) {
      for (var a = set[i]; a; a = a.parentElement) {
        if (marked.has(a)) break;
        marked.add(a);
      }
    }
    marked.forEach(function (m) {
      if (inputs.has(m)) return;
      for (var c = m.firstElementChild; c; c = c.nextElementSibling) {
        if (!marked.has(c) && c.localName !== "head") out.push(c);
      }
    });
    return out;
  }
  function filter(set, fn) {
    var out = [];
    for (var i = 0; i < set.length; i++) if (fn(set[i])) out.push(set[i]);
    return out;
  }
  // mode: 0 top-level, 1 has-subchain (set=[e]), 2 not-subchain (set=[e])
  function run(chain, set, mode) {
    for (var i = 0; i < chain.length; i++) {
      var c = chain[i];
      if (mode === 1 && i === 0 && c.op !== "css" && c.op !== "xpath") {
        set = Array.prototype.slice.call(set[0].querySelectorAll("*"));
      }
      set = step(c, set, mode === 1 && i === 0);
      if (set && !set.length) return set;
    }
    return set || [];
  }
  function step(c, set, hasFirst) {
    var out, i;
    switch (c.op) {
      case "css":
        if (set === null) return Array.prototype.slice.call(D.querySelectorAll(c.s));
        out = new Set();
        for (i = 0; i < set.length; i++) {
          if (hasFirst && c.rel) rel(set[i], c.rel, c.s.slice(1).trim(), out);
          else qsaInto(set[i], c.s, out);
        }
        return uniq(out);
      case "spath":
        if (set === null) set = [D.documentElement];
        out = new Set();
        for (i = 0; i < set.length; i++) rel(set[i], c.comb, c.rest, out);
        return uniq(out);
      case "matches-path":
        return c.p.test(location.pathname + location.search) ? set : [];
      case "matches-media":
        return c.m.matches ? set : [];
      case "watch-attr":
        return set;
      case "xpath":
        out = new Set();
        var ctx = set === null ? [D] : set;
        for (i = 0; i < ctx.length; i++) {
          var r = D.evaluate(c.x, ctx[i], null, 7 /* ORDERED_NODE_SNAPSHOT_TYPE */, null);
          for (var j = 0; j < r.snapshotLength; j++) {
            var n = r.snapshotItem(j);
            if (n && n.nodeType === 1) out.add(n);
          }
        }
        return uniq(out);
    }
    if (set === null) set = Array.prototype.slice.call(D.querySelectorAll("*"));
    switch (c.op) {
      case "matches":
        return filter(set, function (e) { return e.matches(c.s); });
      case "has":
        if (c.sub.length === 1 && c.sub[0].op === "css" && !c.sub[0].rel) {
          var s0 = c.sub[0].s;
          return filter(set, function (e) { return e.querySelector(s0) !== null; });
        }
        return filter(set, function (e) { return run(c.sub, [e], 1).length > 0; });
      case "not":
        return filter(set, function (e) { return run(c.sub, [e], 2).length === 0; });
      case "has-text":
        return filter(set, function (e) { return c.p.test(textOf(e)); });
      case "min-text-length":
        return filter(set, function (e) { return textOf(e).length >= c.n; });
      case "matches-attr":
        return filter(set, function (e) {
          var at = e.attributes;
          for (var k = 0; k < at.length; k++) {
            if (c.np.test(at[k].name) && (!c.vp || c.vp.test(at[k].value))) return true;
          }
          return false;
        });
      case "matches-css":
        return filter(set, function (e) {
          return c.p.test(W.getComputedStyle(e, c.pseudo).getPropertyValue(c.prop));
        });
      case "matches-prop":
        return filter(set, function (e) {
          var v = e;
          for (var k = 0; k < c.chain.length; k++) {
            if (v === null || v === undefined || !(c.chain[k] in Object(v))) return false;
            v = v[c.chain[k]];
          }
          return c.p ? c.p.test(String(v)) : true;
        });
      case "others":
        return others(set);
      case "upward":
        out = new Set();
        for (i = 0; i < set.length; i++) {
          var e = set[i];
          if (c.s) { e = e.parentElement; e = e && e.closest(c.s); }
          else for (var k = 0; e && k < c.n; k++) e = e.parentElement;
          if (e) out.add(e);
        }
        return uniq(out);
    }
    return [];
  }
  function protectedEl(e) { return e === D.documentElement || e === D.body || e === D.head; }
  function procPass() {
    timer = 0;
    var t0 = now();
    lastPass = t0;
    var hide = [], styles = [];
    for (var i = 0; i < procs.length; i++) {
      var p = procs[i], els;
      try { els = run(p.t, null, 0); } catch (e) { els = []; }
      if (!els.length && p.a && p.a.k !== "style") continue;
      if (!p.a) { for (var j = 0; j < els.length; j++) hide.push(els[j]); continue; }
      try {
        switch (p.a.k) {
          case "style": styles.push([p.a.decl, els]); break;
          case "remove":
            els.forEach(function (e) { if (!protectedEl(e)) e.remove(); });
            break;
          case "remove-attr":
            els.forEach(function (e) {
              var names = [];
              for (var k = 0; k < e.attributes.length; k++) if (p.a.p.test(e.attributes[k].name)) names.push(e.attributes[k].name);
              names.forEach(function (n) { e.removeAttribute(n); });
            });
            break;
          case "remove-class":
            els.forEach(function (e) {
              var cs = [];
              for (var k = 0; k < e.classList.length; k++) if (p.a.p.test(e.classList[k])) cs.push(e.classList[k]);
              if (cs.length) e.classList.remove.apply(e.classList, cs);
            });
            break;
        }
      } catch (e) {}
    }
    hideT = hide;
    styleT = styles;
    syncProc();
    var dt = now() - t0;
    ST.passes++;
    ST.passMs += dt;
    // adaptive spacing: procedural work stays below ~1/9 of main-thread time during mutation storms
    gap = Math.min(2000, Math.max(D.readyState === "loading" ? 100 : 50, dt * 8));
  }
  var timer = 0, lastPass = -1e9, gap = 50;
  function schedule(force) {
    if (!procs.length || !deep || !D.documentElement) return;
    if (force && timer) { clearTimeout(timer); timer = 0; }
    var wait = force ? 0 : lastPass + gap - now();
    if (wait <= 0 && !timer) { procPass(); return; }
    if (!timer) timer = setTimeout(procPass, Math.max(0, wait));
  }

  // procedural targets -> structural selectors (no DOM marks). Recomputed after every mutation batch.
  var pathParents = new Set(), ppNext = null;
  function path(e) {
    var root = D.documentElement, parts = [];
    while (e && e !== root) {
      var p = e.parentElement;
      if (!p) return null;
      if (ppNext) ppNext.add(p);
      parts.push(":nth-child(" + idx(e) + ")");
      e = p;
    }
    if (!e) return null;
    return parts.length ? ":root > " + parts.reverse().join(" > ") : ":root";
  }
  function chunked(sels, body, out) {
    for (var i = 0; i < sels.length; i += 200) out.push(sels.slice(i, i + 200).join(",") + body);
  }
  function procRuleTexts() {
    ppNext = new Set();
    idxCache = new Map();
    try { return procRuleTexts2(); } finally { pathParents = ppNext; ppNext = null; idxCache = null; }
  }
  function procRuleTexts2() {
    var out = [];
    if (hideT.length) {
      var set = new Set();
      hideT.forEach(function (e) { if (e.isConnected) set.add(e); });
      var groups = new Map();
      set.forEach(function (e) {
        for (var a = e.parentElement; a; a = a.parentElement) if (set.has(a)) return;   // ancestor already hidden
        var p = e.parentElement || null, g = groups.get(p);
        if (!g) groups.set(p, g = []);
        g.push(e);
      });
      var single = [];
      groups.forEach(function (kids, p) {
        if (p && kids.length >= 8) {
          var keep = [], ks = new Set(kids);
          for (var c = p.firstElementChild; c; c = c.nextElementSibling) if (!ks.has(c)) keep.push(c);
          if (keep.length <= 4) {
            var pp = path(p);
            ppNext.add(p);
            if (pp) {
              out.push(pp + " > *" + keep.map(function (k) { return ":not(:nth-child(" + idx(k) + "))"; }).join("") + HIDE);
              return;
            }
          }
        }
        kids.forEach(function (k) { var s = path(k); if (s) single.push(s); });
      });
      chunked(single, HIDE, out);
    }
    styleT.forEach(function (st) {
      var sels = [];
      st[1].forEach(function (e) { if (e.isConnected) { var s = path(e); if (s) sels.push(s); } });
      if (sels.length) chunked(sels, "{" + st[0] + "}", out);
    });
    return out;
  }
  function syncProc() {
    var rules = procRuleTexts();
    if (rules.length === procRules.length && rules.every(function (r, i) { return r === procRules[i]; })) return;
    procRules = rules;
    if (!sheet || sheet.cssRules.length !== expLen) { rebuild(); return; }
    try {
      for (var i = 0; i < procCount; i++) sheet.deleteRule(0);
      expLen -= procCount;
      var n = 0;
      for (var j = 0; j < rules.length; j++) {
        try { sheet.insertRule(rules[j], n); n++; } catch (e) {}
      }
      procCount = n;
      expLen += n;
    } catch (e) { rebuild(); return; }
    ensure();
  }

  // ------------------------------------------------------------------ plain :remove()
  function rmEl(e) { if (!protectedEl(e)) e.remove(); }
  function removeIn(n) {
    if (!removeSel) return;
    if (n === D) { var l = D.querySelectorAll(removeSel); for (var i = 0; i < l.length; i++) rmEl(l[i]); return; }
    if (n.matches(removeSel)) { rmEl(n); return; }
    if (n.firstElementChild) {
      var m = n.querySelectorAll(removeSel);
      for (var j = 0; j < m.length; j++) rmEl(m[j]);
    }
  }

  // ------------------------------------------------------------------ configuration (idempotent)
  function configure(d) {
    if (!d || typeof d !== "object") d = {};
    data = d;
    flags = d.flags | 0;
    var off = (flags & 12) !== 0;          // EHIDE | DOC
    genOn = !off && !(flags & 1);          // GHIDE
    specOn = !off && !(flags & 2);         // SHIDE
    survey = genOn && !!SR;
    if (!survey) pend = [];
    hostUnhide = new Set(arr(d.unhide));
    var base = [], rm = [], ps = [], info = {attrs: new Set(), any: false, path: false};
    if (specOn) {
      arr(d.hide).forEach(function (s) {
        if (str(s) && !hostUnhide.has(s) && valid(s)) base.push(s + HIDE);
      });
      arr(d.style).forEach(function (p) {
        if (!Array.isArray(p)) return;
        var s = p[0], decl = p[1];
        if (str(s) && okDecl(decl) && !hostUnhide.has(s + ":style(" + decl + ")") && valid(s)) base.push(s + "{" + decl + "}");
      });
      arr(d.remove).forEach(function (s) {
        if (str(s) && !hostUnhide.has(s + ":remove()") && valid(s)) { rm.push(s); base.push(s + HIDE); }
      });
      arr(d.proc).forEach(function (p) {
        if (p && hostUnhide.has(p.s)) return;
        try { ps.push(cproc(p, info)); } catch (e) {}
      });
    }
    if (genOn) {
      for (var i = 0; i < high.length; i++) {
        var s = high[i];
        if (str(s) && !genUnhide.has(s) && !hostUnhide.has(s) && s.indexOf("{") < 0 && s.indexOf("}") < 0) base.push(s + OFF);
      }
    }
    baseRules = base;
    lowRules = [];
    if (genOn) lowAll.forEach(function (s) { if (!genUnhide.has(s) && !hostUnhide.has(s)) lowRules.push(s + OFF); });
    removeSel = rm.join(",");
    procs = ps;
    hideT = [];
    styleT = [];
    procRules = [];
    rebuild();
    setupWatch(info);
    if (deep) {
      if (survey) fullScan();
      removeIn(D);
      if (procs.length) schedule(true);
    }
    if (survey) {
      // tokens seen before configuration (or while generic was off) are queried now
      pend = [];
      seen.forEach(function (t) { if (!sent.has(t)) pend.push(t); });
      flushTokens();
    }
  }

  function setupWatch(info) {
    watchInfo = info;
    if (!deep) return;
    if (watchMO) { watchMO.disconnect(); watchMO = null; }
    if (info.any || info.attrs.size) {
      watchMO = new MutationObserver(function () {
        try { schedule(false); } catch (e) {}
      });
      var o = {attributes: true, subtree: true};
      if (!info.any) o.attributeFilter = Array.from(info.attrs);
      watchMO.observe(D, o);
    }
    if (info.path && !navHooked) {
      navHooked = true;
      var re = function () { try { schedule(true); } catch (e) {} };
      W.addEventListener("popstate", re);
      W.addEventListener("hashchange", re);
      try { if (W.navigation) W.navigation.addEventListener("currententrychange", re); } catch (e) {}
    }
  }

  // ------------------------------------------------------------------ main observer
  function onMut(recs) {
    var t0 = now(), pm0 = ST.passMs;
    try {
      if (!data) configure({});
      var structural = false, moved = false;
      for (var i = 0; i < recs.length; i++) {
        var r = recs[i];
        if (r.type === "childList") {
          structural = true;
          if (!moved && pathParents.has(r.target)) {
            // pure appends after the last element child keep every existing :nth-child index
            var ns = r.nextSibling;
            if (r.removedNodes.length || (ns && (ns.nodeType === 1 || ns.nextElementSibling))) moved = true;
          }
          var a = r.addedNodes;
          for (var j = 0; j < a.length; j++) {
            var n = a[j];
            if (n.nodeType !== 1) continue;
            if (survey) collect(n);
            if (removeSel && n.isConnected) removeIn(n);
          }
        } else if (survey && r.target.nodeType === 1) {
          tok(r.target);
        }
      }
      ST.survMs += now() - t0;
      if (survey && pend.length) flushTokens();
      // structural selectors of procedural targets only move when a parent on their path changed
      var lp = lastPass;
      if (structural && procs.length) schedule(false);
      if (moved && lp === lastPass) syncProc();
      ensure();
    } catch (e) {}
    ST.cb++;
    ST.ms += now() - t0 - (ST.passMs - pm0);   // ms excludes procedural passes (counted in passMs)
  }

  // No MutationObserver while the parser runs: merely registering one (even shallow, even if disconnected
  // later) slows Blink's parser for the rest of the document (measured +80 ms DCL on a 5k-element page).
  // Declarative CSS (specific + high generic) is active from DocumentCreation; surveyor, procedural filters
  // and :remove() go live at DOMContentLoaded, or 1 s after document creation on slow pages.
  var mo = null, deep = false, early = 0, watchInfo = null;
  function goDeep() {
    if (deep || !D.documentElement) return;
    deep = true;
    if (early) { clearTimeout(early); early = 0; }
    mo.observe(D, {childList: true, subtree: true, attributes: true, attributeFilter: ["class", "id"]});
    if (watchInfo) setupWatch(watchInfo);
  }
  function onReady() {
    var t0 = now(), pm0 = ST.passMs;
    try {
      if (!data) configure({});
      if (!D.documentElement) return;
      var fresh = !deep;
      goDeep();
      if (fresh || !scanned) { if (survey) fullScan(); }
      if (survey && pend.length) flushTokens();
      removeIn(D);
      schedule(true);
      ensure();
    } catch (e) {}
    ST.ms += now() - t0 - (ST.passMs - pm0);
  }

  G.__lc = function (d) { try { configure(d); } catch (e) {} };
  try {
    mo = new MutationObserver(onMut);
    D.addEventListener("DOMContentLoaded", onReady);
    W.addEventListener("load", onReady);
    if (G.__lcq) { var q = G.__lcq; G.__lcq = undefined; configure(q); }
    // per-host data is injected right after this script (same DocumentCreation pass; a microtask would run
    // in between); if none came by the next task, use defaults
    if (!data) setTimeout(function () { if (!data) G.__lc({}); }, 0);
    if (D.readyState !== "loading") setTimeout(onReady, 0);     // started late (existing about:blank frame etc.)
    else early = setTimeout(function () { early = 0; onReady(); }, 1000);
  } catch (e) {}
}
