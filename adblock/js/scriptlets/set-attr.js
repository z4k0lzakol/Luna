// @world: main
// set-attr: set-attr(selector, attr, [value]). value: "" (default), true, false, integer 0..32767, or
// "[other]" = copy attribute "other" of the same element; anything else -> inert. Runs when the DOM is ready,
// then on DOM mutations (re-applies when the page changes the attribute back). Spec 03c 5.
// Internal form (used by trusted-set-attr): first argument {trusted: true} -> any value.
// Event-handler attributes (on*), srcdoc, script/object/embed URL attributes and javascript: values are refused.
function (R, ...args) {
  var trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    trusted = args[0].trusted === true;
    args = R.slice(args, 1);
  }
  var A = R.safeArgs(args, 3, ["log", "debug"], 2);
  var n = R.n, doc = R.doc;
  var sel = R.trim(A.p[0]), attr = R.lower(R.trim(A.p[1])), value = A.p[2];
  if (sel === "" || attr === "") return;
  if (R.startsWith(attr, "on") || attr === "srcdoc" || R.apply(n.reTest, /[\s"'>\/=]/, [attr])) return;
  var copyFrom = null;
  if (!trusted) {
    var m = R.apply(n.reExec, /^\[([^\]\s]+)\]$/, [value]);
    if (m) copyFrom = m[1];
    else if (!(value === "" || value === "true" || value === "false" ||
               (R.apply(n.reTest, /^\d+$/, [value]) && n.Number(value) < 32768))) return;
  }
  if (copyFrom === null && R.apply(n.reTest, /^\s*(?:javascript|vbscript|data\s*:\s*text\/html)/i, [value])) return;
  try { R.apply(n.querySelectorAll, doc, [sel]); } catch (e) { return; }
  var URLISH = ["src", "href", "xlink:href", "data", "codebase", "action", "formaction"];
  var queued = false;

  function apply1(el) {
    var nm = R.nodeName(el);
    if ((nm === "SCRIPT" || nm === "OBJECT" || nm === "EMBED") && R.apply(n.aIndexOf, URLISH, [attr]) !== -1) return;
    var v = value;
    if (copyFrom !== null) {
      var c = null;
      try { c = R.apply(n.getAttribute, el, [copyFrom]); } catch (e) { return; }
      if (c === null) return;
      if (R.apply(n.reTest, /^\s*(?:javascript|vbscript)\s*:/i, [c])) return;
      v = c;
    }
    try {
      if (R.apply(n.getAttribute, el, [attr]) !== v) R.apply(n.setAttribute, el, [attr, v]);
    } catch (e) { /* ignore */ }
  }
  function pass() {
    queued = false;
    var list;
    try { list = R.toArray(R.apply(n.querySelectorAll, doc, [sel])); } catch (e) { return; }
    for (var i = 0; i < list.length; i++) apply1(list[i]);
  }
  function queue() {
    if (queued) return;
    queued = true;
    R.apply(n.queueMicrotask, R.win, [pass]);
  }
  R.onReady(function () {
    pass();
    var filt = copyFrom !== null ? [attr, copyFrom] : [attr];
    R.observe(doc, { childList: true, subtree: true, attributes: true, attributeFilter: filt }, queue);
  }, "interactive");
}
