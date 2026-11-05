// @world: main
// lib-json: internal helper of SCRIPTLETS-1 (not a filter-list name; lists cannot invoke it).
// Legacy json-prune paths (spec 02 §14), uBO-flavoured JSONPath for the edit family (02 §15, 03b §9.1, legacy and
// "v2:"), vararg parser. Usage: var J = R.deps["lib-json"](R);  (one instance per realm, cached on R)
//   J.pruner(prunePaths, needlePaths) -> fn(obj) -> changed | null when prunePaths is empty
//   J.path(query, trusted) -> {run(root) -> changed} | null when invalid (or an assignment from an untrusted list)
//   J.va(args, npos, names) -> {p: [npos strings], x: {name: value}}   (varargs may follow empty slots)
//   J.parse(text) / J.stringify(value) with the pristine JSON functions (throw like the natives)
function (R) {
  if (R.xjson) return R.xjson;
  var n = R.n, apply = R.apply, win = R.win;
  var isArray = n.isArray, okeys = n.keys, aSplice = n.aSplice, JSONo = win.JSON;
  var JP = n.JSON_parse, JS = n.JSON_stringify, RX = n.RegExp, reTest = n.reTest, reExec = n.reExec;
  var sSlice = n.sSlice, sTrim = n.sTrim, sStarts = n.sStartsWith, sEnds = n.sEndsWith, sIncl = n.sIncludes;
  var sReplace = n.sReplace, sSplit = n.sSplit, SetC = n.Set, setHas = n.Set.prototype.has, setAdd = n.Set.prototype.add;
  var MapC = n.Map, mapGet = n.Map.prototype.get, mapSet = n.Map.prototype.set, mapForEach = n.Map.prototype.forEach;
  var create = n.create, NUM = n.Number, STR = n.String, aSort = win.Array.prototype.sort;
  var J = {};
  R.xjson = J;
  // "a.b.c" -> {o: owner object, p: "c"} resolved now (methods must exist at install time), or null
  J.owner = function (chain) {
    var parts = apply(sSplit, trim(R.str(chain)), ["."]), o = win;
    for (var i = 0; i < parts.length; i++) if (parts[i] === "") return null;
    for (i = 0; i < parts.length - 1; i++) {
      try { o = o[parts[i]]; } catch (e) { return null; }
      if (!isObj(o)) return null;
    }
    return { o: o, p: parts[parts.length - 1] };
  };

  function isObj(v) { return v !== null && (typeof v === "object" || typeof v === "function"); }
  function slice(s, a, b) { return apply(sSlice, s, b === undefined ? [a] : [a, b]); }
  function trim(s) { return apply(sTrim, s, []); }
  function push(a, v) { a[a.length] = v; }
  function has(o, k) { try { return isObj(o) && (k in o); } catch (e) { return false; } }
  function keysOf(o) {
    try {
      if (isArray(o)) { var a = []; for (var i = 0; i < o.length; i++) a[i] = "" + i; return a; }
      return okeys(o);
    } catch (e) { return []; }
  }
  function getv(o, k) { try { return o[k]; } catch (e) { return undefined; } }
  function del(o, k) {
    try {
      if (isArray(o) && apply(reTest, /^\d+$/, [k])) { apply(aSplice, o, [NUM(k), 1]); return true; }
      return delete o[k];
    } catch (e) { return false; }
  }
  J.parse = function (t) { return apply(JP, JSONo, [t]); };
  J.stringify = function (v) { return apply(JS, JSONo, [v]); };
  J.isObj = isObj;

  // ---------------------------------------------------------------- varargs
  J.va = function (args, npos, names) {
    var a = [], i, out = { p: [], x: create(null) };
    for (i = 0; i < (args ? args.length : 0); i++) a[i] = R.str(args[i]);
    var start = npos;
    for (i = 1; i < npos && i < a.length; i++) {
      if (apply(n.aIndexOf, names, [a[i]]) !== -1) { start = i; break; }
    }
    for (i = 0; i < npos; i++) out.p[i] = i < start && i < a.length ? a[i] : "";
    for (i = start; i < a.length; ) {
      if (apply(n.aIndexOf, names, [a[i]]) !== -1) { out.x[a[i]] = i + 1 < a.length ? a[i + 1] : ""; i += 2; }
      else i++;
    }
    return out;
  };

  // ---------------------------------------------------------------- legacy prune paths
  function segsOf(spec) {
    var out = [], parts = apply(sSplit, trim(R.str(spec)), [/\s+/]);
    for (var i = 0; i < parts.length; i++) if (parts[i] !== "") push(out, apply(sSplit, parts[i], ["."]));
    return out;
  }
  function isIter(seg) { return seg === "[]" || seg === "*" || seg === "[-]" || seg === "{-}"; }
  function exists(node, segs, i) {
    if (!isObj(node)) return false;
    var seg = segs[i], last = i === segs.length - 1;
    if (isIter(seg)) {
      if ((seg === "[]" || seg === "[-]") && !isArray(node)) return false;
      var ks = keysOf(node);
      if (last) return ks.length > 0;
      for (var k = 0; k < ks.length; k++) if (exists(getv(node, ks[k]), segs, i + 1)) return true;
      return false;
    }
    if (!has(node, seg)) return false;
    return last ? true : exists(getv(node, seg), segs, i + 1);
  }
  function clearAll(node) {
    var ch = false;
    if (isArray(node)) { if (node.length) { apply(aSplice, node, [0, node.length]); ch = true; } return ch; }
    var ks = keysOf(node);
    for (var k = 0; k < ks.length; k++) if (del(node, ks[k])) ch = true;
    return ch;
  }
  function pruneAt(node, segs, i) {
    if (!isObj(node)) return false;
    var seg = segs[i], last = i === segs.length - 1, ch = false, ks, k;
    if (seg === "[]" || seg === "*") {
      if (seg === "[]" && !isArray(node)) return false;
      if (last) return clearAll(node);
      ks = keysOf(node);
      for (k = 0; k < ks.length; k++) if (pruneAt(getv(node, ks[k]), segs, i + 1)) ch = true;
      return ch;
    }
    if (seg === "[-]" || seg === "{-}") {
      if (last || (seg === "[-]") !== !!isArray(node)) return false;
      ks = keysOf(node);
      for (k = ks.length - 1; k >= 0; k--) {
        if (exists(getv(node, ks[k]), segs, i + 1) && del(node, ks[k])) ch = true;
      }
      return ch;
    }
    if (!has(node, seg)) return false;
    if (last) return del(node, seg);
    return pruneAt(getv(node, seg), segs, i + 1);
  }
  J.pruner = function (pruneSpec, needleSpec) {
    var P = segsOf(pruneSpec), N = segsOf(needleSpec);
    if (!P.length) return null;
    return function (obj) {
      if (!isObj(obj)) return false;
      var i;
      for (i = 0; i < N.length; i++) if (!exists(obj, N[i], 0)) return false;
      var ch = false;
      for (i = 0; i < P.length; i++) if (pruneAt(obj, P[i], 0)) ch = true;
      return ch;
    };
  };

  // ---------------------------------------------------------------- JSONPath
  var OPS = ["==", "!=", "<=", ">=", "^=", "$=", "*=", "=", "<", ">"];
  function opAt(s, i) {
    for (var k = 0; k < OPS.length; k++) if (apply(sStarts, s, [OPS[k], i])) return OPS[k];
    return "";
  }
  function scanRegex(s, i) {   // s[i] === "/" -> index after the flags, or -1
    var j = i + 1, cls = false;
    for (; j < s.length; j++) {
      var c = s[j];
      if (c === "\\") { j++; continue; }
      if (cls) { if (c === "]") cls = false; continue; }
      if (c === "[") { cls = true; continue; }
      if (c === "/") break;
    }
    if (j >= s.length || j === i + 1) return -1;
    var k = j + 1;
    while (k < s.length && apply(reTest, /[a-z]/, [s[k]])) k++;
    return k;
  }
  function mkRe(lit) {
    var m = apply(reExec, /^\/([\s\S]+)\/([a-z]*)$/, [lit]);
    if (!m) return null;
    try { return new RX(m[1], apply(sReplace, m[2], [/[^imsu]/g, ""])); } catch (e) { return null; }
  }
  function reHit(re, s) { re.lastIndex = 0; return apply(reTest, re, [s]); }
  function scanClose(s, i, close) {   // s[i] is the opening char -> index of the matching close, or -1
    var depth = 0, q = "", open = s[i];
    for (var j = i; j < s.length; j++) {
      var c = s[j];
      if (q) { if (c === "\\") j++; else if (c === q) q = ""; continue; }
      if (c === '"' || c === "'") { q = c; continue; }
      if (c === "/" && j > i && (s[j - 1] === "=" || s[j - 1] === "[" || s[j - 1] === ".")) {
        var e = scanRegex(s, j);
        if (e > 0) { j = e - 1; continue; }
      }
      if (c === open) depth++;
      else if (c === close) { depth--; if (depth === 0) return j; }
    }
    return -1;
  }
  function readName(s, i, cond) {
    var j = i;
    while (j < s.length) {
      var c = s[j];
      if (c === "." || c === "[") break;
      if (!cond && (c === "=" || (c === "+" && s[j + 1] === "="))) break;
      if (cond && (c === " " || c === "\t" || opAt(s, j) !== "")) break;
      j++;
    }
    return j;
  }
  function parseCond(s, v2) {
    s = trim(s);
    var neg = false;
    if (s.charAt(0) === "!") { neg = true; s = trim(slice(s, 1)); }
    var pp = parsePath(s, 0, true, v2);
    if (!pp) return null;
    var j = pp.i;
    while (j < s.length && (s[j] === " " || s[j] === "\t")) j++;
    var c = { path: pp.steps, op: "", neg: neg, val: undefined, re: null };
    if (j >= s.length) return c;
    var op = opAt(s, j);
    if (!op) return null;
    var rest = trim(slice(s, j + op.length));
    if (op === "=") {
      c.op = "re"; c.re = mkRe(rest);
      return c.re ? c : null;
    }
    c.op = op;
    try { c.val = J.parse(rest); } catch (e) { return null; }
    return c;
  }
  function parseBracket(inner, v2) {
    var t = trim(inner);
    if (t.charAt(0) === "?") {
      var c = parseCond(slice(t, 1), v2);
      return c ? { t: v2 ? "cf" : "f", c: c } : null;
    }
    if (t === "*") return { t: "c*" };
    if (apply(reTest, /^-?\d+$/, [t])) return { t: "idx", n: NUM(t) };
    if (t.length >= 2 && (t.charAt(0) === "'" || t.charAt(0) === '"') && t.charAt(t.length - 1) === t.charAt(0)) {
      if (t.charAt(0) === '"') { try { return { t: "c", k: STR(J.parse(t)) }; } catch (e) { return null; } }
      return { t: "c", k: slice(t, 1, t.length - 1) };
    }
    if (t.charAt(0) === "/") { var re = mkRe(t); return re ? { t: "cre", re: re } : null; }
    return null;
  }
  // -> {steps, i} (i = where parsing stopped: end, assignment, operator) or null
  function parsePath(s, i, cond, v2) {
    var steps = [], start;
    if (s[i] === "$" || (cond && s[i] === "@")) i++;
    start = i;
    while (i < s.length) {
      var c = s[i], desc = false;
      if (c !== "." && c !== "[") {
        if (i !== start || steps.length) break;   // a bare leading name: "a.b" == ".a.b"
        var j0 = readName(s, i, cond);
        if (j0 === i) break;
        push(steps, { t: "c", k: slice(s, i, j0) });
        i = j0;
        continue;
      }
      if (c === ".") {
        if (s[i + 1] === ".") { desc = true; i += 2; } else i += 1;
        c = s[i];
        if (c === "*") { push(steps, { t: desc ? "d*" : "c*" }); i++; continue; }
        if (c === "/") {
          var e = scanRegex(s, i);
          if (e < 0) return null;
          var re = mkRe(slice(s, i, e));
          if (!re) return null;
          push(steps, { t: desc ? "dre" : "cre", re: re });
          i = e;
          continue;
        }
        if (c !== "[") {
          var j = readName(s, i, cond);
          if (j === i) { if (desc) { push(steps, { t: "d*" }); continue; } return null; }
          push(steps, { t: desc ? "d" : "c", k: slice(s, i, j) });
          i = j;
          continue;
        }
      }
      var end = scanClose(s, i, "]");
      if (end < 0) return null;
      var st = parseBracket(slice(s, i + 1, end), v2);
      if (!st) return null;
      if (desc) push(steps, { t: "dself" });
      push(steps, st);
      i = end + 1;
    }
    return { steps: steps, i: i };
  }

  var LIMIT = 200000;
  function walk(root, fn) {   // every (parent, key) below root, depth-first, cycle-safe
    var seen = new SetC(), stack = [root], count = 0;
    while (stack.length && count < LIMIT) {
      var o = stack[stack.length - 1];
      stack.length--;
      if (!isObj(o) || apply(setHas, seen, [o])) continue;
      apply(setAdd, seen, [o]);
      var ks = keysOf(o);
      for (var i = 0; i < ks.length; i++) {
        count++;
        fn(o, ks[i]);
        var v = getv(o, ks[i]);
        if (isObj(v)) stack[stack.length] = v;
      }
    }
  }
  function mkRef(p, k) { return { p: p, k: k, v: getv(p, k) }; }
  function testCond(c, v) {
    var refs = evalSteps(c.path, [{ p: null, k: null, v: v }]), r = false;
    if (!c.op) r = refs.length > 0;
    else for (var i = 0; i < refs.length && !r; i++) r = cmp(refs[i].v, c);
    return c.neg ? !r : r;
  }
  function cmp(x, c) {
    var y = c.val, tx = typeof x;
    switch (c.op) {
      case "==": return x === y;
      case "!=": return x !== y;
      case "<": case "<=": case ">": case ">=":
        if (!((tx === "number" || tx === "string") && tx === typeof y)) return false;
        return c.op === "<" ? x < y : c.op === "<=" ? x <= y : c.op === ">" ? x > y : x >= y;
      case "^=": return tx === "string" && apply(sStarts, x, [R.str(y)]);
      case "$=": return tx === "string" && apply(sEnds, x, [R.str(y)]);
      case "*=": return tx === "string" && apply(sIncl, x, [R.str(y)]);
      case "re": return (tx === "string" || tx === "number") && reHit(c.re, STR(x));
    }
    return false;
  }
  function stepOne(st, rf, out) {
    var v = rf.v, t = st.t, ks, i;
    if (t === "f") { if (testCond(st.c, v)) push(out, rf); return; }
    if (!isObj(v)) return;
    if (t === "c") { if (has(v, st.k)) push(out, mkRef(v, st.k)); return; }
    if (t === "idx") {
      var ix = st.n;
      if (isArray(v) && ix < 0) ix = v.length + ix;
      if (ix >= 0 && has(v, "" + ix)) push(out, mkRef(v, "" + ix));
      return;
    }
    if (t === "c*" || t === "cre" || t === "cf") {
      ks = keysOf(v);
      for (i = 0; i < ks.length; i++) {
        if (t === "cre" && !reHit(st.re, ks[i])) continue;
        var cr = mkRef(v, ks[i]);
        if (t === "cf" && !testCond(st.c, cr.v)) continue;
        push(out, cr);
      }
      return;
    }
    if (t === "dself") push(out, rf);
    walk(v, function (p, k) {
      if (t === "d" && k !== st.k) return;
      if (t === "dre" && !reHit(st.re, k)) return;
      push(out, mkRef(p, k));
    });
  }
  function evalSteps(steps, refs) {
    for (var s = 0; s < steps.length && refs.length; s++) {
      var out = [];
      for (var r = 0; r < refs.length; r++) stepOne(steps[s], refs[r], out);
      refs = out;
    }
    return refs;
  }
  function removeRefs(refs) {
    var groups = new MapC(), ch = false;
    for (var i = 0; i < refs.length; i++) {
      var r = refs[i];
      if (r.p === null) continue;
      var g = apply(mapGet, groups, [r.p]);
      if (!g) { g = []; apply(mapSet, groups, [r.p, g]); }
      if (apply(n.aIndexOf, g, [r.k]) === -1) push(g, r.k);
    }
    apply(mapForEach, groups, [function (g, p) {
      if (isArray(p)) {
        var idx = [];
        for (var a = 0; a < g.length; a++) if (apply(reTest, /^\d+$/, [g[a]])) push(idx, NUM(g[a]));
        apply(aSort, idx, [function (x, y) { return y - x; }]);
        for (var b = 0; b < idx.length; b++) { try { apply(aSplice, p, [idx[b], 1]); ch = true; } catch (e) { /* ignore */ } }
      } else {
        for (var c = 0; c < g.length; c++) if (del(p, g[c])) ch = true;
      }
    }]);
    return ch;
  }
  function nowFill(text) {
    return apply(sReplace, text, [/\$\{now\}/g, function () { return STR(R.now()); }]);
  }
  // assignment text after "=" / "+=" -> action or null (unsupported)
  function parseAction(op, text) {
    text = trim(text);
    var m = apply(reExec, /^repl\(([\s\S]*)\)$/, [text]);
    if (m && op === "=") {
      var o;
      try { o = J.parse(m[1]); } catch (e) { return null; }
      if (!isObj(o)) return null;
      var rep = typeof o.replacement === "string" ? o.replacement : "", re = null, lit = null;
      if (typeof o.regex === "string") {
        re = mkRe(o.regex);
        if (!re) { try { re = new RX(o.regex); } catch (e) { return null; } }
        if (re && !re.global && o.regex.charAt(0) !== "/") re = new RX(re.source, re.flags + "g");
      } else if (typeof o.pattern === "string" && o.pattern !== "") lit = o.pattern;
      else return null;
      return { t: "repl", re: re, lit: lit, rep: rep };
    }
    if (apply(reTest, /^call\(/, [text])) return null;
    try { J.parse(nowFill(text)); } catch (e) { return null; }
    return { t: op === "+=" ? "merge" : "set", text: text };
  }
  function makeVal(act) { return J.parse(nowFill(act.text)); }
  function doAction(refs, act) {
    var ch = false;
    for (var i = 0; i < refs.length; i++) {
      var r = refs[i];
      try {
        if (act.t === "set") {
          if (r.p === null) continue;
          r.p[r.k] = makeVal(act);
          ch = true;
        } else if (act.t === "merge") {
          var src = makeVal(act);
          if (!isObj(r.v) || isArray(r.v) || !isObj(src)) continue;
          var ks = okeys(src);
          for (var k = 0; k < ks.length; k++) r.v[ks[k]] = src[ks[k]];
          ch = true;
        } else if (act.t === "repl") {
          if (r.p === null || typeof r.v !== "string") continue;
          var nv;
          if (act.re) { act.re.lastIndex = 0; nv = apply(sReplace, r.v, [act.re, act.rep]); }
          else nv = apply(n.aJoin, apply(sSplit, r.v, [act.lit]), [act.rep]);
          if (nv !== r.v) { r.p[r.k] = nv; ch = true; }
        }
      } catch (e) { /* ignore */ }
    }
    return ch;
  }
  function splitTop(s, sep) {
    var out = [], q = "", depth = 0, last = 0;
    for (var j = 0; j < s.length; j++) {
      var c = s[j];
      if (q) { if (c === "\\") j++; else if (c === q) q = ""; continue; }
      if (c === '"' || c === "'") { q = c; continue; }
      if (c === "/" && j > 0 && (s[j - 1] === "=" || s[j - 1] === "[" || s[j - 1] === ".")) {
        var e = scanRegex(s, j);
        if (e > 0) { j = e - 1; continue; }
      }
      if (c === "[" || c === "(" || c === "{") depth++;
      else if (c === "]" || c === ")" || c === "}") depth--;
      else if (c === sep && depth === 0) { push(out, slice(s, last, j)); last = j + 1; }
    }
    push(out, slice(s, last));
    return out;
  }
  // full query (with optional assignment) -> {steps, act} | null
  function compileOne(q, v2, trusted) {
    var pp = parsePath(q, 0, false, v2);
    if (!pp || !pp.steps.length) return null;
    var i = pp.i, act = null;
    if (i < q.length) {
      var op = q[i] === "=" ? "=" : (q[i] === "+" && q[i + 1] === "=") ? "+=" : "";
      if (!op || !trusted) return null;
      act = parseAction(op, slice(q, i + op.length));
      if (!act) return null;
    }
    return { steps: pp.steps, act: act };
  }
  J.path = function (query, trusted) {
    var q = trim(R.str(query)), v2 = false, pre = [];
    if (q === "") return null;
    if (apply(sStarts, q, ["v2:"])) {
      v2 = true;
      var parts = splitTop(slice(q, 3), ";");
      for (var i = 0; i < parts.length - 1; i++) {
        var p = trim(parts[i]), lo = 1, hi = Infinity;
        var m = apply(reExec, /\{(\d*)(,?)(\d*)\}$/, [p]);
        if (m) {
          p = slice(p, 0, p.length - m[0].length);
          lo = m[1] !== "" ? NUM(m[1]) : 0;
          hi = m[2] ? (m[3] !== "" ? NUM(m[3]) : Infinity) : lo;
          if (m[1] === "" && !m[2]) return null;
        }
        var pp = parsePath(trim(p), 0, false, true);
        if (!pp || pp.i !== trim(p).length) return null;
        push(pre, { steps: pp.steps, lo: lo, hi: hi });
      }
      q = trim(parts[parts.length - 1]);
    }
    var main = compileOne(q, v2, trusted);
    if (!main) return null;
    return {
      run: function (root) {
        if (!isObj(root)) return false;
        var base = [{ p: null, k: null, v: root }];
        for (var k = 0; k < pre.length; k++) {
          var cnt = evalSteps(pre[k].steps, base).length;
          if (cnt < pre[k].lo || cnt > pre[k].hi) return false;
        }
        var refs = evalSteps(main.steps, base);
        if (!refs.length) return false;
        return main.act ? doAction(refs, main.act) : removeRefs(refs);
      }
    };
  };
  return J;
}
