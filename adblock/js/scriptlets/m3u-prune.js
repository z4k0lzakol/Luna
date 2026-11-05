// @deps: lib-net
// @world: main
// m3u-prune: (needle, [urlNeedle]). fetch / XHR responses whose URL matches urlNeedle ("" = all) and whose text
// starts with #EXTM3U are edited:
//  * needle = regex with the m flag (whole-text mode): every match (g added) is removed together with the rest of
//    the line it starts in; a match that ends inside a line is left alone (never part of a line);
//  * otherwise (line mode): a matching URI line is removed with the segment tags right above it (#EXTINF,
//    #EXT-X-DISCONTINUITY, #EXT-X-BYTERANGE, ... but never playlist header tags); a matching tag line alone.
// Unchanged playlists keep the original response. Spec 03b 11.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["log", "debug"], 2);
  var needle = A.p[0];
  if (needle === "") return;
  var N = R.deps["lib-net"](R), n = R.n;
  var P = R.pattern(needle, false), UP = R.pattern(A.p[1], false);
  var whole = null;
  if (P.kind === "regex" && R.includes(P.re.flags, "m")) {
    try { whole = new n.RegExp(P.re.source, R.includes(P.re.flags, "g") ? P.re.flags : P.re.flags + "g"); } catch (e) { return; }
  }
  var HEAD = ["#EXTM3U", "#EXT-X-VERSION", "#EXT-X-TARGETDURATION", "#EXT-X-MEDIA-SEQUENCE", "#EXT-X-PLAYLIST-TYPE",
              "#EXT-X-ENDLIST", "#EXT-X-INDEPENDENT-SEGMENTS", "#EXT-X-START", "#EXT-X-DISCONTINUITY-SEQUENCE",
              "#EXT-X-I-FRAMES-ONLY", "#EXT-X-ALLOW-CACHE"];
  function isHeader(l) {
    var t = R.split(l, ":")[0];
    return R.apply(n.aIndexOf, HEAD, [t]) !== -1;
  }
  function wholeMode(text) {
    var cuts = [], m, len = text.length;
    whole.lastIndex = 0;
    while ((m = R.apply(n.reExec, whole, [text])) !== null) {
      var s = m.index, e = s + m[0].length;
      if (m[0] === "") { whole.lastIndex = s + 1; continue; }
      var ls = s;
      while (ls > 0 && text.charAt(ls - 1) !== "\n") ls--;
      var endsNL = text.charAt(e - 1) === "\n";
      if (!(e === len || endsNL || text.charAt(e) === "\n")) continue;
      if (!endsNL && e < len) e++;   // take the line break too
      if (cuts.length && ls < cuts[cuts.length - 1][1]) ls = cuts[cuts.length - 1][1];
      if (ls < e) R.push(cuts, [ls, e]);
    }
    if (!cuts.length) return null;
    var out = "", pos = 0;
    for (var i = 0; i < cuts.length; i++) { out += R.slice(text, pos, cuts[i][0]); pos = cuts[i][1]; }
    return out + R.slice(text, pos);
  }
  function lineMode(text) {
    var lines = R.split(text, "\n"), drop = [], ch = false, i, j;
    for (i = 0; i < lines.length; i++) {
      var l = lines[i], t = R.trim(l);
      if (t === "" || !P.test(t)) continue;
      if (t.charAt(0) === "#") {
        if (!isHeader(t)) { drop[i] = true; ch = true; }
        continue;
      }
      drop[i] = true; ch = true;
      for (j = i - 1; j >= 0; j--) {
        var u = R.trim(lines[j]);
        if (!R.startsWith(u, "#EXT") || isHeader(u)) break;
        drop[j] = true;
      }
    }
    if (!ch) return null;
    var keep = [];
    for (i = 0; i < lines.length; i++) if (!drop[i]) R.push(keep, lines[i]);
    return R.join(keep, "\n");
  }
  N.editResponse({
    kind: "text",
    test: function (req) { return UP.test(req.url); },
    run: function (text) {
      if (!R.apply(n.reTest, /^[\s﻿]*#EXTM3U/, [text])) return null;
      return whole ? wholeMode(text) : lineMode(text);
    }
  }, "both");
}
