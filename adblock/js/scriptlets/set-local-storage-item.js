// @world: main
// set-local-storage-item: (key, value). value from a closed set (integers -32767..32767, '', undefined, null,
// true/false/on/off/yes/no, consent tokens, {}, [], "", optionally double-quoted -> stored with the quotes) or
// $remove$. A /regex/ key with $remove$ removes every matching key. Spec 03c 12.1.
// Internal form (shared by set-session-storage-item, trusted-set-*-storage-item): first argument
// {session: bool, trusted: bool}. Trusted: any value, $now$ / $currentDate$ / $currentISODate$ placeholders.
function (R, ...args) {
  var session = false, trusted = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    session = args[0].session === true;
    trusted = args[0].trusted === true;
    args = R.slice(args, 1);
  }
  var n = R.n, win = R.win;
  var A = R.safeArgs(args, 2, ["log", "debug"], 2);
  var key = A.p[0], value = A.p[1];
  if (key === "") return;
  var TOKENS = ["", "undefined", "null", "false", "true", "on", "off", "yes", "no", "accept", "reject", "accepted",
    "rejected", "allowed", "denied", "notaccepted", "allow", "disallow", "deny", "approved", "disapproved", "checked",
    "unchecked", "dismiss", "dismissed", "enable", "disable", "enabled", "disabled", "essential", "nonessential",
    "forbidden", "forever", "hide", "hidden", "necessary", "required", "ok", "t", "f", "y", "n", "all", "none",
    "functional", "granted", "done", "decline", "declined", "closed", "next", "mandatory", "disagree", "agree",
    "{}", "[]", '""', "$remove$"];
  if (!trusted) {
    var inner = value;
    if (inner.length >= 2 && inner.charAt(0) === '"' && inner.charAt(inner.length - 1) === '"') inner = R.slice(inner, 1, -1);
    var ok;
    if (R.apply(n.reTest, /^-?\d+$/, [inner])) {
      var num = n.Number(inner);
      ok = num >= -32767 && num <= 32767;
    } else {
      ok = R.apply(n.aIndexOf, TOKENS, [inner]) !== -1 || R.apply(n.aIndexOf, TOKENS, [R.lower(inner)]) !== -1;
    }
    if (!ok) return;
  } else if (value !== "$remove$" && R.includes(value, "$")) {
    var D = win.Date;
    var toISO = D.prototype.toISOString, toStr = D.prototype.toString;
    value = R.sreplace(value, /\$(now|currentDate|currentISODate)\$/g, function (m, k) {
      var t = R.now();
      if (k === "now") return n.String(t);
      try { return R.apply(k === "currentDate" ? toStr : toISO, new D(t), []); } catch (e) { return m; }
    });
  }
  var st;
  try {
    var f = R.findDesc(win, session ? "sessionStorage" : "localStorage");
    st = f && f.desc.get ? R.apply(f.desc.get, win, []) : null;
  } catch (e) { return; }   // opaque / sandboxed origin
  if (!st) return;
  var SP = win.Storage.prototype;
  var setItem = SP.setItem, removeItem = SP.removeItem, keyFn = SP.key;
  var lenGet = n.getOwnPropertyDescriptor(SP, "length").get;
  if (value === "$remove$") {
    var KP = R.pattern(key, false);
    if (KP.kind === "regex") {
      var hits = [];
      try {
        var len = R.apply(lenGet, st, []);
        for (var i = 0; i < len; i++) {
          var k = R.apply(keyFn, st, [i]);
          if (k !== null && KP.test(k)) R.push(hits, k);
        }
      } catch (e) { return; }
      for (var j = 0; j < hits.length; j++) { try { R.apply(removeItem, st, [hits[j]]); } catch (e) { /* ignore */ } }
      return;
    }
    try { R.apply(removeItem, st, [key]); } catch (e) { /* ignore */ }
    return;
  }
  try { R.apply(setItem, st, [key, value]); } catch (e) { /* quota / denied */ }
}
