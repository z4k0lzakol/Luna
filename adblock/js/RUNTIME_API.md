# Luna scriptlet runtime — API for scriptlet authors

Files: `adblock/js/runtime.js` (the runtime), `adblock/scriptlets.py` (bundle builder),
`adblock/scriptlet_names.py` (name tables), `adblock/js/scriptlets/<canonical-name>.js` (one file per scriptlet).
Tests: `tests/adblock/test_scriptlets.py` (pure Python), `tests/adblock/test_runtime_qt.py` (real QtWebEngine:
MainWorld + DocumentCreation + subframes, strict CSP + enforced Trusted Types, stealth checks). Copy the Qt test's
pattern (one page, `T` result object, baseline host without scriptlets) for new scriptlets.

## 1. Writing a scriptlet file

```js
// @deps: other-name              (optional; comma separated canonical names)
// @world: main
// my-scriptlet (alias): my(argA, [argB]); varargs foo. Spec 03x N.
function (R, ...args) {
  var A = R.safeArgs(args, 2, ["foo", "log", "debug"], 1);
  if (A.p[0] === "") return;                 // invalid/empty required argument -> stay inert
  ...
}
```

* Exactly **one function expression** `function (R, ...args) { ... }`. Header lines must be `//` comments; full-line
  `//` comments and indentation are stripped by the builder (so never start a line inside a string/regex with `//`,
  and never use template literals that span lines).
* `args` are always **strings** (JSON-encoded by the builder; never spliced into code). Use the rest parameter, never
  `arguments` spread or `...x` in calls (spread uses the page-patchable array iterator).
* The file name is the canonical name from `scriptlet_names.KNOWN`. After writing it, add the name to **your** block
  in `scriptlet_names.SUPPORTED` (`# --- SCRIPTLETS-n ---`). `canonical()`/`ALIASES` already map all aliases.
* Trusted-only names (`trusted-*`, `rpnt`, ...) are dropped by the builder for untrusted lists; your code does not
  re-check trust.
* `@deps`: the dependency's function is bundled once and callable as `R.deps["other-name"](R, ...)`. Convention for
  shared implementations (used by `prevent-setInterval`, `adjust-setInterval`): pass an **options object as the first
  argument** (lists can only pass strings, so an object is unambiguous):
  ```js
  // @deps: prevent-setTimeout
  function (R, ...args) {
    R.apply(R.deps["prevent-setTimeout"], null, R.apply(R.n.aConcat, [R, { target: "setInterval" }], [args]));
  }
  ```
  `set-constant` accepts `{trusted: true}` the same way (trusted value parser, no type guard) — use it for
  `trusted-set-constant`.
* The bundle runs every invocation inside `try {} catch (e) {}`; still never let page-visible errors escape.

### Stealth rules (critic P0-3, spec 02)
1. No `eval`, `Function`, string timers, `<script>` text/`innerHTML`/`outerHTML`/`srcdoc`/`script.src`/`object.data`
   writes — all are CSP or Trusted Types sinks and get reported to the site (verified: `object data` is a
   TrustedScriptURL sink). Remove/retype/clone nodes instead (`R.emptyScript`, `R.onScriptInsert`).
2. No `console`, no `debugger`, no globals, no DOM markers/attributes for bookkeeping.
3. Patch natives only via `R.wrapMethod` / `R.wrapCtor` / `R.wrapAccessor` / `R.proxy` / `R.trap` (all masked).
   Functions you create and expose to the page: wrap with `R.fn(f, "source text it should show")`.
4. Call natives through saved references: `R.apply(R.n.xxx, thisArg, [args])`. Capture extra natives **at install
   time** (top of your function), e.g. `var get = R.n.getOwnPropertyDescriptor(R.win.Response.prototype, "url").get;`
   — install time is document creation, before any page script.
5. Never run page code inside a wrapper unless the semantics require it: stringify callbacks with `R.fnText`, other
   values with `R.str` (objects -> `""`).
6. Always reach the page through `R.win` / `R.doc` (never free `window`/`document`): the same function is re-run for
   same-origin child realms (about:blank iframes, see §9) with a different `R`.
7. Function names show up in stacks when page code runs inside our frames: keep names neutral (`anon` via `R.anon`).

## 2. Bundle shape and lifecycle (scriptlets.py)

```python
from adblock import scriptlets
scriptlets.configure(sr=SR)              # glue: scheme base "x<hex>://l/<token>/" -> R.SR
js = scriptlets.build([(name, [args], trusted), ...], host)   # -> str | None
scriptlets.available()                   # names with a .js file
scriptlets.runtime_source(); scriptlets.SECRET; scriptlets.clear_cache()
```
`build()` canonicalises names, drops unknown / unimplemented / trusted-only-from-untrusted rules and rules with an
argument > 64 KB, keeps at most 32 arguments, de-duplicates `(name, args)` keeping list order, and emits:
```js
(function(){"use strict";var M=function (win, SR, SECRET, S) {...runtime...};var R=M(window,"<SR>","<SECRET>",null);
var a0=function (R, ...args) {...};          // implementations used (deps first), neutral names a0..aN
var D={"prevent-setTimeout":a0};             // deps map
R.boot(function(R){R.deps=D;
try{a1(R,"x","y");}catch(e){}
},M);})();
```
The glue wraps it with the host guard and appends `\n//# sourceURL=<anonymous>`; script name must be empty (no
`userscript:` frames). `R.boot` runs the invocations once per realm, then (if anything was masked) installs the
`Function.prototype.toString` mask and the frame hooks.

Measured cost (QtWebEngine 6.11, this machine): ~3 ms first-call compile of the runtime per document, ~5–8 ms
total with 3–12 scriptlets; second instantiation 0.1 ms. Zero cost on hosts without scriptlets.

## 3. Natives: `R.n`, `R.win`, `R.doc`, `R.SR`, `R.apply`

All captured from `win` when the runtime starts (document creation). Call them with `R.apply(fn, thisArg, argsArray)`
(`R.apply === R.n.apply === Reflect.apply`).

| group | members |
|---|---|
| Reflect/Object | `apply construct defineProperty getOwnPropertyDescriptor getPrototypeOf setPrototypeOf ownKeys has get set` (Reflect versions: `defineProperty` returns bool), `create keys entries freeze assign hasOwn` (`hasOwn` = `Object.prototype.hasOwnProperty`, use via apply) |
| JSON | `JSON_parse JSON_stringify` (call with `R.apply(R.n.JSON_parse, R.win.JSON, [s])`) |
| Array | `isArray aSlice aPush aJoin aIndexOf aSplice aConcat aMap aFilter aForEach aIncludes` |
| String | `sIncludes sIndexOf sSlice sSplit sReplace sStartsWith sEndsWith sTrim sToLowerCase sToUpperCase sCharCodeAt fromCharCode String Number Boolean` |
| RegExp | `RegExp reTest reExec` |
| ctors | `Proxy WeakMap WeakSet Map Set Promise promiseResolve promiseReject promiseThen Error TypeError ReferenceError captureStackTrace URL URLSearchParams TextEncoder TextDecoder DOMParser XMLSerializer Blob fetch Request Response Headers XMLHttpRequest MutationObserver HTMLScriptElement HTMLElement Element Node Document Window` |
| timers | `queueMicrotask setTimeout clearTimeout setInterval clearInterval requestAnimationFrame` (call with `R.win` as this) |
| misc | `Date_now Math_random Math_floor Math_min Math_max atob btoa encodeURIComponent decodeURIComponent FTS` (native `Function.prototype.toString`), `location` |
| events | `addEventListener removeEventListener dispatchEvent preventDefault stopImmediatePropagation` |
| DOM methods | `querySelector querySelectorAll createElement getElementById createTreeWalker twNext` (Document), `elQuerySelector elQuerySelectorAll fragQuerySelectorAll matches closest getAttribute setAttribute removeAttribute hasAttribute remove replaceWith cloneNode appendChild contains getComputedStyle getBoundingClientRect moObserve moDisconnect` |
| DOM getters/setters | `nodeTypeGet nodeNameGet parentNodeGet textContentGet textContentSet nodeValueGet nodeValueSet isConnectedGet defaultViewGet currentScriptGet readyStateGet documentElementGet headGet bodyGet cookieGet cookieSet scriptSrcGet scriptTypeGet iframeContentWindowGet objectContentWindowGet` |

`R.SR` = scheme base URL string (`""` if the glue has none). XHR/fetch fakes retarget to `R.SR + "x/" + ...`
(SCRIPTLETS-1 defines the encoding; the custom scheme ignores page CSP).

## 4. Masking (`Function.prototype.toString`)

* `R.mask(fake, nativeFnOrText) -> fake` — registers `fake` so `Function.prototype.toString` prints like
  `nativeFnOrText` (a function: its native text, e.g. `function setTimeout() { [native code] }`; a string: exactly that
  text). The toString Proxy is installed lazily, once per realm, and masks itself
  (`toString.toString()` -> `function toString() { [native code] }`); invalid receivers throw the native TypeError with
  a stack identical to the native one. Wrapping a wrapper is fine (registrations collapse to the innermost native).
* `R.fn(f, text) -> f` — for functions **you create** (not proxies): sets their prototype to this realm's
  `Function.prototype` and masks them with `text` (default `"function () {}"`).
* `R.anon(fnExpr) -> fnExpr` — `var f = R.anon(function () {})` keeps `f.name === ""` (plain `var f = function(){}`
  would be named `"f"`).
* One registry is shared by the whole same-origin frame tree: a parent page calling its own `toString` on a child
  frame's wrapper (and the reverse) gets native text (verified).

## 5. Wrapping and defining

* `R.wrapMethod(obj, prop, h) -> proxy | null` — `obj[prop]` (own or inherited function) becomes a masked
  `Proxy(target, {apply: h})`, `h(target, thisArg, argsArray)`. Descriptor attributes are kept (inherited -> own
  property on `obj` with the same attributes); `name`, `length`, own keys, `new` behaviour unchanged.
  ```js
  R.wrapMethod(R.win, "setTimeout", function (t, th, a) {
    if (hit(a)) { var b = R.slice(a, 0); b[0] = noop; return R.apply(t, th, b); }
    return R.apply(t, th, a);
  });
  ```
  The args array `a` is a fresh array; copy with `R.slice(a, 0)` before changing it.
* `R.wrapCtor(obj, prop, hConstruct, hApply?) -> proxy | null` — `hConstruct(target, args, newTarget)`
  (use `R.n.construct(target, args, newTarget)` to forward).
* `R.wrapAccessor(obj, prop, {get: h, set: h}) -> bool` — replaces the getter/setter of an accessor (own or on the
  prototype that owns it — the descriptor is redefined on its holder) with masked proxies;
  `h(nativeGetter, thisArg, [])` / `h(nativeSetter, thisArg, [value])`. Example (mask `responseURL`):
  ```js
  R.wrapAccessor(R.win.XMLHttpRequest.prototype, "responseURL", { get: function (t, th, a) {
    var f = R.apply(wmGet, fakes, [th]); return f !== undefined ? f : R.apply(t, th, a); } });
  ```
* `R.proxy(target, handler) -> proxy` — masked Proxy with any handler.
* `R.redefine(obj, prop, value) -> bool` — set a data value keeping the attributes (non-configurable writable ->
  plain assignment).
* `R.defineAccessor(obj, prop, getf(receiver), setf(receiver, v), enumerable) -> {get, set} | null` — configurable
  accessor whose functions are named `get prop` / `set prop` and print as
  `function get prop() { [native code] }`.
* `R.findDesc(obj, prop) -> {desc, holder, own} | null` — walks the prototype chain.

## 6. Property-chain traps: `R.trap(owner, chain, spec) -> bool`

`chain` = `"a.b.c"` relative to `owner` (normally `R.win`). Intermediate objects that do not exist yet are trapped and
the leaf is installed when they are assigned (works for `var x = {...}`, step-by-step creation, `JSON.parse` results;
several traps under the same missing parent compose). The leaf becomes a configurable accessor (keeps enumerable).

```js
spec = {
  defer: "any" | "strict" | "none",   // "any" (default): trap any missing parent;
                                      // "strict" (set-constant): only absent / own data parents, never shadow
                                      //   inherited accessors (e.g. document.body before <body>) -> give up;
                                      // "none" (acs): trap the FIRST missing segment itself as the leaf
  init(st)  -> false to give up,      // optional, before defining
  get(st, receiver) -> value,         // optional, default R.passGet
  set(st, value, receiver),           // optional, default R.passSet
  fixed(owner, prop, desc) -> bool    // optional: leaf exists and is non-configurable (else: give up)
}
st = { owner, prop, desc /* original descriptor found on the chain or undefined */, own, value /* data value */,
       fnGet, fnSet /* the accessor functions the page calls — pass to R.abort / R.stack */ }
```
* `R.passGet(st, receiver)` / `R.passSet(st, value, receiver)` — behave like the original property (original
  getter/setter with the real receiver; data values stored in `st.value`; writes through an inheriting object create
  an own data property on it).
* Inherent limits (as uBO): a top-level `function x(){}` replaces a window trap; `let/const/class x` shadow it;
  page `Object.defineProperty` wins (traps stay configurable on purpose).

Examples: `abort-on-property-read.js`, `abort-current-script.js`, `set-constant.js`.

## 7. Aborts and stacks

* `R.abort(msg, above)` — throws a page-realm `ReferenceError(msg)` whose stack starts at the page frame that called
  `above` (pass `st.fnGet`/`st.fnSet` or your trap function), i.e. it looks exactly like a real
  `ReferenceError: x is not defined`. If uncaught, the `error` event is swallowed before page listeners /
  `window.onerror` and nothing reaches the console (verified); unhandled promise rejections with it are swallowed too.
* `R.abortMsg(chain) -> "<lastSegment> is not defined"`.
* `R.stack(above) -> "stackDepth:N\tfn@url:L:1\t..."` — normalised stack of the page code that called `above`
  (frames of `above` and everything inside it are omitted). Inline-document frames -> `inlineScript`, eval /
  `<anonymous>` frames -> `injectedScript`, `async `/`new `/` [as x]` stripped, column forced to 1, builtin frames
  without a position skipped. `Error.prepareStackTrace` / `stackTraceLimit` (50) are neutralised during capture.
  Verified: a read from `function probeFn` called by an inline script gives
  `stackDepth:2\tprobeFn@inlineScript:L:1\t@inlineScript:L:1`. Guard against re-entrancy (see `abort-on-stack-trace.js`).

## 8. Arguments, patterns, constants

* `R.safeArgs(args, npos, varargNames, req) -> {p: [npos strings], x: {name: value}}` — positional slots padded with
  `""`; name/value pairs after them (`x` has no prototype; missing value -> `""`; later duplicates win). Early start
  (spec 01 §9): an optional slot `k >= req` holding a known vararg name starts the varargs there
  (`set, x, y, runAt, interactive`). `req` default 1.
* `R.pattern(raw, negatable) -> P` — `""` = all; `/re/flags` (flags `gimsu`, non-empty body, valid) = regex; else
  case-sensitive substring; `!` prefix only when `negatable`. `P.test(text)` (lastIndex-safe), `P.kind`
  (`"all" | "literal" | "regex"`), `P.neg`, `P.text`, `P.re` (with original flags, e.g. for replace).
* `R.exactPattern(raw)` — like `pattern` but literal = whole-string equality (aeld event types).
* `R.delayMatcher(raw) -> fn(d)->bool | null` — `""` any, `N`, `A-B`, `A-`, `-B`, `!` negation; null = unparseable.
* `R.delayOf(v)` — timer delay as the browser sees it without running page code (non-numeric objects -> 0).
* `R.constant(raw, trusted, chain) -> {v} | null` — spec 02 §4 table (`undefined false true null '' "" noopFunc
  trueFunc falseFunc throwFunc noopCallbackFunc noopPromiseResolve noopPromiseReject [] {} emptyArr emptyObj yes no`,
  integers -32767..32767). Trusted extras: `json:<JSON>`, `{"value": ...}`, otherwise the raw string. Each call makes
  fresh objects/functions (call once per invocation). Generated functions are masked (`function () {}` etc.).

## 9. Strings and misc helpers

`R.str(v)` (primitive -> String, else `""`), `R.fnText(x)` (function source via native toString / primitive / `""`),
`R.includes(s, sub)`, `R.indexOf(s, sub)`, `R.split(s, sep)`, `R.slice(stringOrArray, a, b?)`, `R.trim(s)`,
`R.lower(s)`, `R.startsWith(s, p)`, `R.endsWith(s, p)`, `R.sreplace(s, patternOrRe, replacementOrFn)`,
`R.push(arr, v)`, `R.join(arr, sep)`, `R.toArray(arrayLike)`, `R.isObj(v)`, `R.now()`,
`R.later(fn, ms) -> id` (pristine `setTimeout` with a function; exceptions swallowed), `R.log()` (no-op, never logs).

## 10. DOM helpers

* `R.readyState()`; `R.onReady(fn, when)` — `""/loading/1` now; `interactive/end/2` at DOMContentLoaded;
  `complete/idle/3` at load (now if already reached).
* `R.nodeName(n)`, `R.nodeType(n)`, `R.parent(n)`, `R.isScript(n)`, `R.text(n)` (element textContent / node
  nodeValue), `R.isExecutableScript(el)` (type absent or a JS MIME / module).
* `R.setText(node, text) -> bool` — writes non-script text; **refuses `<script>` (and text nodes inside one)**
  because that is a Trusted Types sink.
* `R.emptyScript(el) -> clone | null` — replaces a not-yet-executed script with an empty shallow clone (same
  attributes, no text, nothing executes, no TT/CSP sink). Use from a MutationObserver for parser-inserted scripts.
* `R.observe(target, options, cb(records)) -> stop()` — pristine MutationObserver.
* `R.onScriptInsert(fn(scriptEl) -> true to block) -> remove()` — wraps the insertion APIs once per realm
  (`appendChild insertBefore replaceChild append prepend before after replaceWith insertAdjacentElement
  replaceChildren` on Node/Element/Document/DocumentFragment/CharacterData) and inspects `<script>` elements in the
  inserted nodes/fragments; blocked scripts get `type="text/plain"` during the native insertion and the original
  type back afterwards (they never run; no TT sink; verified with TT-created scripts).
* `R.onWrite(fn(html) -> html) -> remove()` — edits plain-string `document.write/writeln` calls (TrustedHTML
  arguments pass through untouched).

## 11. Frames and realms

* `R.ancestorHosts() -> [hostname...]` (parent first, from `location.ancestorOrigins`), `R.ancestorHost()`,
  `R.isTop()`.
* DOM bypass: when anything was masked, `contentWindow`/`contentDocument` getters of iframe/frame/object are hooked;
  the first access to a same-origin child realm (e.g. a script-created `about:blank` iframe) synchronously
  re-runs this host's invocations there (new `R` with that realm's natives) and masks its `toString` — verified:
  `iframe.contentWindow.setTimeout` is defused too and the fresh frame's `toString` prints native text.
  `window[0]`/`frames[0]` access cannot be intercepted (residual). `R.adopt(win)` does it manually (used by the
  `nowoif` decoy).
* Internal: `R.S` (shared state), `R.boot`, `R.M`, `R.run`, `R.deps` — do not touch except `R.deps`.

## 12. Known residuals (accepted, as in uBO)

Accessor descriptors on trapped properties; own accessor on `document` for `acs, document.x`; our frames appear in
stacks while native code calls back into page code from inside a wrapper (spec 02 §7.4); `Error.prepareStackTrace`
swap during `R.stack` is observable by a page that installs accessors there; decoy iframes are visible in
`window.length`; the private ancestor probe calls a same-origin parent's `toString` with a secret receiver only when
it already looks like a Proxy of the native.
