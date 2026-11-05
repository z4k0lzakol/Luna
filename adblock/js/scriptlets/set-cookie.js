// @world: main
// set-cookie: set-cookie(name, value, [path]); varargs reload, dontOverwrite, domain. value from a closed
// token set (or integer -32767..32767), optionally wrapped in double quotes (kept). Session cookie. Spec 03c 11.1.
// Internal form (shared by set-cookie-reload, trusted-set-cookie[-reload]): first argument
// {trusted: bool, reload: bool}. Trusted signature: (name, value, [expiresOffset], [path]); any value with
// $now$ / $currentDate$ / $currentISODate$ placeholders; domain may be /regex/ run on location.hostname.
function (R, ...args) {
  var trusted = false, forceReload = false;
  if (args.length && args[0] !== null && typeof args[0] === "object") {
    trusted = args[0].trusted === true;
    forceReload = args[0].reload === true;
    args = R.slice(args, 1);
  }
  var n = R.n, win = R.win, doc = R.doc;
  var A = R.safeArgs(args, trusted ? 4 : 3, ["reload", "dontOverwrite", "domain", "log", "debug"], 2);
  var name = R.trim(A.p[0]), value = A.p[1];
  if (name === "") return;
  var expires = trusted ? R.trim(A.p[2]) : "", path = trusted ? A.p[3] : A.p[2];
  var TOKENS = ["accept", "reject", "accepted", "rejected", "notaccepted", "allow", "disallow", "deny", "allowed",
    "denied", "approved", "disapproved", "checked", "unchecked", "dismiss", "dismissed", "enable", "disable",
    "enabled", "disabled", "essential", "nonessential", "forbidden", "forever", "hide", "hidden", "necessary",
    "required", "ok", "on", "off", "true", "t", "false", "f", "yes", "y", "no", "n", "all", "none", "functional",
    "granted", "done", "decline", "declined", "closed", "next", "mandatory", "disagree", "agree"];
  if (!trusted) {
    var inner = value;
    if (inner.length >= 2 && inner.charAt(0) === '"' && inner.charAt(inner.length - 1) === '"') inner = R.slice(inner, 1, -1);
    var ok = false;
    if (R.apply(n.reTest, /^-?\d+$/, [inner])) {
      var num = n.Number(inner);
      ok = num >= -32767 && num <= 32767;
    } else {
      ok = R.apply(n.aIndexOf, TOKENS, [R.lower(inner)]) !== -1;
    }
    if (!ok) return;
  } else if (R.includes(value, "$")) {
    var D = win.Date, dnow = n.Date_now;
    var toISO = D.prototype.toISOString, toStr = D.prototype.toString;
    value = R.sreplace(value, /\$(now|currentDate|currentISODate)\$/g, function (m, k) {
      var t = R.apply(dnow, D, []);
      if (k === "now") return n.String(t);
      try { return R.apply(k === "currentDate" ? toStr : toISO, new D(t), []); } catch (e) { return m; }
    });
  }
  var host = "";
  try { host = R.str(win.location.hostname); } catch (e) { host = ""; }
  var domain = A.x.domain !== undefined ? R.trim(A.x.domain) : "";
  if (domain !== "") {
    var DP = R.pattern(domain, false);
    if (DP.kind === "regex") {
      if (!trusted) return;
      DP.re.lastIndex = 0;
      var dm = R.apply(n.reExec, DP.re, [host]);
      if (!dm) return;
      domain = dm[0];
    }
    if (R.apply(n.reTest, /[;,\s=]/, [domain])) return;
  }
  // encoding (RFC 6265 octets / RFC 7230 token)
  var encName = R.apply(n.reTest, /^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/, [name]) ? name : n.encodeURIComponent(name);
  var encValue = R.apply(n.reTest, /^[\x20-\x3A\x3C-\x5B\x5D-\x7E]*$/, [value]) ? value : n.encodeURIComponent(value);
  function current() {
    var all = "";
    try { all = R.str(R.apply(n.cookieGet, doc, [])); } catch (e) { return null; }
    var parts = R.split(all, ";");
    for (var i = 0; i < parts.length; i++) {
      var p = R.trim(parts[i]);
      var k = R.indexOf(p, "=");
      var nm = k === -1 ? "" : R.slice(p, 0, k);
      var vl = k === -1 ? p : R.slice(p, k + 1);
      if (nm === encName) return vl;
    }
    return null;
  }
  var before = current();
  if (before !== null) {
    if (A.x.dontOverwrite !== undefined && A.x.dontOverwrite !== "" && A.x.dontOverwrite !== "0") return;
    if (before === encValue) return;
  }
  var c = encName + "=" + encValue;
  if (expires !== "" && expires !== "0") {
    var secs = NaN;
    if (expires === "1day") secs = 86400;
    else if (expires === "1year") secs = 31536000;
    else if (R.apply(n.reTest, /^\d+$/, [expires])) secs = n.Number(expires);
    if (secs === secs && secs > 0) {
      try {
        var DD = win.Date;
        c += "; expires=" + R.apply(DD.prototype.toUTCString, new DD(R.now() + secs * 1000), []);
      } catch (e) { /* session cookie */ }
    }
  }
  var hostPrefix = R.startsWith(name, "__Host-");
  if (path !== "none" || hostPrefix) c += "; path=/";
  if (domain !== "" && !hostPrefix) c += "; domain=" + domain;
  if (hostPrefix || R.startsWith(name, "__Secure-")) c += "; Secure";
  try { R.apply(n.cookieSet, doc, [c]); } catch (e) { return; }
  var reload = forceReload || (A.x.reload !== undefined && A.x.reload !== "" && A.x.reload !== "0");
  if (reload && before !== encValue && current() === encValue) {
    // location.reload() at document creation is ignored by Chromium; one task later it works (verified)
    var loc = win.location, rl = loc.reload;
    R.later(function () { R.apply(rl, loc, []); }, 0);
  }
}
