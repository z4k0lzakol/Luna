// @world: main
// remove-cache-storage-item: (cacheNameNeedle, [urlNeedle]) - semantics UNVERIFIED (spec 03c 12.3), Luna design:
// at document start, in Cache Storage caches whose name matches cacheNameNeedle (pattern; empty = every cache)
// delete the entries whose request URL matches urlNeedle, or the whole cache when urlNeedle is empty.
// Both empty -> inert. Asynchronous; all promise rejections are handled.
function (R, ...args) {
  var A = R.safeArgs(args, 2, [], 2);
  var nameN = A.p[0], urlN = A.p[1];
  if (nameN === "" && urlN === "") return;
  var n = R.n, win = R.win;
  var cs;
  try { cs = win.caches; } catch (e) { return; }
  if (!R.isObj(cs) || typeof win.CacheStorage !== "function" || typeof win.Cache !== "function") return;
  var CSP = win.CacheStorage.prototype, CP = win.Cache.prototype;
  var csKeys = CSP.keys, csOpen = CSP.open, csDelete = CSP["delete"];
  var cKeys = CP.keys, cDelete = CP["delete"];
  var uD = R.findDesc(win.Request.prototype, "url");
  if (!uD || !uD.desc.get) return;
  var urlGet = uD.desc.get;
  var NP = R.pattern(nameN, false), UP = R.pattern(urlN, false);
  var ignore = R.anon(function () {});
  function then(p, ok) {
    var safe = function (v) { try { ok(v); } catch (e) { /* ignore */ } };
    try { return R.apply(n.promiseThen, p, [safe, ignore]); } catch (e) { return null; }
  }
  function cleanCache(name) {
    if (urlN === "") { then(R.apply(csDelete, cs, [name]), ignore); return; }
    then(R.apply(csOpen, cs, [name]), function (cache) {
      then(R.apply(cKeys, cache, []), function (reqs) {
        for (var i = 0; i < reqs.length; i++) {
          var u = "";
          try { u = R.apply(urlGet, reqs[i], []); } catch (e) { u = ""; }
          if (UP.test(u)) then(R.apply(cDelete, cache, [reqs[i]]), ignore);
        }
      });
    });
  }
  try {
    then(R.apply(csKeys, cs, []), function (names) {
      for (var i = 0; i < names.length; i++) {
        if (typeof names[i] === "string" && NP.test(names[i])) cleanCache(names[i]);
      }
    });
  } catch (e) { /* ignore */ }
}
