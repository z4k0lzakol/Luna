// @world: main
// trusted-create-html (trusted-create-HTML; trusted only): (parentSelector, html, [durationMs]); vararg runAt.
// Parses html with a small built-in tokenizer (no DOMParser/innerHTML: both are Trusted Types sinks) into
// elements made with createElement(NS)/setAttribute/text nodes, then appends them to the first element matching
// parentSelector (waits for it until load + 2 s when it is not there yet). <script> elements are dropped (they
// would not run from DOMParser either); event-handler attributes are set through the runtime's Trusted Types
// helper; durationMs removes the inserted nodes again. Spec 03c 7.
function (R, ...args) {
  var A = R.safeArgs(args, 3, ["runAt", "log", "debug"], 2);
  var n = R.n, win = R.win, doc = R.doc;
  var parentSel = R.trim(A.p[0]), html = A.p[1];
  if (parentSel === "" || html === "") return;
  try { R.apply(n.querySelectorAll, doc, [parentSel]); } catch (e) { return; }
  var duration = A.p[2] === "" ? 0 : n.Number(A.p[2]);
  if (duration !== duration || duration < 0) duration = 0;
  var createNS = win.Document.prototype.createElementNS, createText = win.Document.prototype.createTextNode;
  var createComment = win.Document.prototype.createComment;
  var appendNode = n.appendChild, removeEl = win.Element.prototype.remove;
  var charRemove = win.CharacterData.prototype.remove, fromCP = win.String.fromCodePoint;
  var HTML_NS = "http://www.w3.org/1999/xhtml", SVG_NS = "http://www.w3.org/2000/svg",
      MATH_NS = "http://www.w3.org/1998/Math/MathML";
  var VOID = ["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"];
  var RAW = ["style", "textarea", "title", "xmp", "noscript", "noembed", "noframes", "iframe"];
  var ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", copy: "©", reg: "®",
              hellip: "…", mdash: "—", ndash: "–", laquo: "«", raquo: "»" };
  function decode(s) {
    if (!R.includes(s, "&")) return s;
    return R.sreplace(s, /&(#x[0-9a-f]+|#\d+|[a-z]+);?/gi, function (m, e) {
      if (e.charAt(0) === "#") {
        var cp = e.charAt(1) === "x" || e.charAt(1) === "X" ? n.Number("0x" + R.slice(e, 2)) : n.Number(R.slice(e, 1));
        if (!(cp > 0 && cp <= 0x10ffff)) return m;
        try { return R.apply(fromCP, win.String, [cp]); } catch (x) { return m; }
      }
      var v = ENT[R.lower(e)];
      return typeof v === "string" && R.apply(n.hasOwn, ENT, [R.lower(e)]) ? v : m;
    });
  }
  // tokenizer -> nodes (in a detached DocumentFragment-like list)
  function build(src) {
    var roots = [], stack = [], i = 0, L = src.length;
    function curParent() { return stack.length ? stack[stack.length - 1] : null; }
    function add(node) {
      var p = curParent();
      if (p) { try { R.apply(appendNode, p.el, [node]); } catch (e) { /* ignore */ } }
      else R.push(roots, node);
    }
    function nsFor(tag) {
      var p = curParent();
      if (tag === "svg") return SVG_NS;
      if (tag === "math") return MATH_NS;
      if (p && p.ns !== HTML_NS && p.tag !== "foreignobject") return p.ns;
      return HTML_NS;
    }
    while (i < L) {
      var lt = R.apply(n.sIndexOf, src, ["<", i]);
      if (lt === -1) lt = L;
      if (lt > i) { add(R.apply(createText, doc, [decode(R.slice(src, i, lt))])); i = lt; continue; }
      if (R.startsWith(R.slice(src, i, i + 4), "<!--")) {
        var ce = R.apply(n.sIndexOf, src, ["-->", i + 4]);
        if (ce === -1) ce = L;
        add(R.apply(createComment, doc, [R.slice(src, i + 4, ce)]));
        i = ce + 3;
        continue;
      }
      if (src.charAt(i + 1) === "!" || src.charAt(i + 1) === "?") {
        var de = R.apply(n.sIndexOf, src, [">", i]);
        i = de === -1 ? L : de + 1;
        continue;
      }
      if (src.charAt(i + 1) === "/") {   // end tag
        var me = R.apply(n.reExec, /^<\/\s*([a-zA-Z][^\s\/>]*)\s*>/, [R.slice(src, i)]);
        if (!me) { add(R.apply(createText, doc, ["<"])); i++; continue; }
        var et = R.lower(me[1]);
        for (var s = stack.length - 1; s >= 0; s--) {
          if (stack[s].tag === et) { stack.length = s; break; }
        }
        i += me[0].length;
        continue;
      }
      var mt = R.apply(n.reExec, /^<([a-zA-Z][^\s\/>]*)/, [R.slice(src, i)]);
      if (!mt) { add(R.apply(createText, doc, ["<"])); i++; continue; }
      var tag = R.lower(mt[1]);
      i += mt[0].length;
      var attrs = [], selfClose = false;
      for (;;) {
        var ma = R.apply(n.reExec, /^\s*(?:(\/)\s*)?(?:([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?)?/, [R.slice(src, i)]);
        if (!ma || ma[0] === "") break;
        i += ma[0].length;
        if (ma[1] && !ma[2]) { selfClose = true; continue; }
        if (ma[2]) {
          var av = ma[3] !== undefined ? ma[3] : ma[4] !== undefined ? ma[4] : ma[5] !== undefined ? ma[5] : "";
          R.push(attrs, [ma[2], decode(av)]);
        }
      }
      var gt = R.apply(n.sIndexOf, src, [">", i]);
      if (gt === -1) gt = L;
      if (src.charAt(gt - 1) === "/") selfClose = true;
      i = gt + 1;
      var ns = nsFor(tag);
      var raw = ns === HTML_NS && (tag === "script" || R.apply(n.aIndexOf, RAW, [tag]) !== -1);
      var rawText = "";
      if (raw) {
        var close = R.apply(n.reExec, new n.RegExp("</" + tag + "\\s*>", "i"), [R.slice(src, i)]);
        var endAt = close ? i + close.index : L;
        rawText = R.slice(src, i, endAt);
        i = close ? endAt + close[0].length : L;
      }
      if (tag === "script") continue;   // never executed by a parser-created fragment either
      var el;
      try { el = R.apply(createNS, doc, [ns, ns === HTML_NS ? tag : mt[1]]); } catch (e) { continue; }
      for (var k = 0; k < attrs.length; k++) {
        var an = attrs[k][0], lan = R.lower(an), val = attrs[k][1];
        if (lan === "srcdoc") continue;
        if (R.apply(n.reTest, /^\s*(?:javascript|vbscript)\s*:/i, [val]) &&
            (lan === "href" || lan === "src" || lan === "action" || lan === "formaction" || lan === "xlink:href")) continue;
        try {
          if (R.startsWith(lan, "on")) {
            var tv = R.trusted("script", val);
            if (tv === null) continue;
            R.apply(n.setAttribute, el, [an, tv]);
          } else R.apply(n.setAttribute, el, [an, val]);
        } catch (e) { /* ignore */ }
      }
      if (raw) {
        if (rawText !== "") {
          var tn = R.apply(createText, doc, [tag === "textarea" || tag === "title" ? decode(rawText) : rawText]);
          try { R.apply(appendNode, el, [tn]); } catch (e) { /* ignore */ }
        }
        add(el);
        continue;
      }
      add(el);
      if (!selfClose && !(ns === HTML_NS && R.apply(n.aIndexOf, VOID, [tag]) !== -1)) {
        R.push(stack, { el: el, tag: tag, ns: ns });
      } else if (selfClose && ns === HTML_NS && R.apply(n.aIndexOf, VOID, [tag]) === -1) {
        R.push(stack, { el: el, tag: tag, ns: ns });   // HTML ignores "/>" on non-void elements
      }
    }
    return roots;
  }
  var inserted = false, unobserve = null;
  function tryInsert() {
    if (inserted) return true;
    var parent = null;
    try { parent = R.apply(n.querySelector, doc, [parentSel]); } catch (e) { parent = null; }
    if (!parent) return false;
    inserted = true;
    if (unobserve) { unobserve(); unobserve = null; }
    var nodes = build(html);
    for (var i = 0; i < nodes.length; i++) { try { R.apply(appendNode, parent, [nodes[i]]); } catch (e) { /* ignore */ } }
    if (duration > 0) {
      R.later(function () {
        for (var j = 0; j < nodes.length; j++) {
          try { R.apply(R.nodeType(nodes[j]) === 1 ? removeEl : charRemove, nodes[j], []); } catch (e) { /* ignore */ }
        }
      }, duration);
    }
    return true;
  }
  function start() {
    if (tryInsert()) return;
    unobserve = R.observe(doc, { childList: true, subtree: true }, function () { tryInsert(); });
    R.onReady(function () {
      R.later(function () { if (unobserve) { unobserve(); unobserve = null; } }, 2000);
    }, "complete");
  }
  R.onReady(start, A.x.runAt !== undefined ? A.x.runAt : "");
}
