# Procedural cosmetic filter AST (site.db `"proc"` entries)

Producer: `adblock/compiler.py` (ENGINE-A). Consumer: `adblock/js/cosmetic.js` / `cosmetic.py` (COSMETIC).
Semantics of every operator: spec `05-procedural-cosmetics.md`. All values are plain JSON.

## Entry

```json
{"s": "<raw selector text>",            // canonical text, used to match #@# exceptions (see below)
 "t": [task, ...],                       // selection chain, evaluated left to right
 "a": action}                            // optional; absent = hide matched elements
```

Only **specific** filters (with a hostname / entity key) produce proc entries. Generic procedural
filters are dropped (uBO semantics).

## Evaluation model

The chain transforms a set of nodes. The top-level chain starts with the set `null` ("no subject yet").

| task | meaning |
|---|---|
| `["css", sel]` | set = `null` -> `document.querySelectorAll(sel)`. Only emitted as the first *selecting* task of a top-level chain, or as the first task of a `has` sub-chain (see below). |
| `["spath", frag]` | `frag` starts with a combinator, normalised to one of `" "`, `" > "`, `" + "`, `" ~ "` followed by the rest, e.g. `" > .x span"`, `" + div"`. For each `e`: combinator `" "`/`" > "` -> `e.querySelectorAll(":scope" + frag)`; `" + "`/`" ~ "` -> `p = e.parentElement; p && p.querySelectorAll(":scope > :nth-child(" + (index(e)+1) + ")" + frag)`. Union, de-duplicated, document order not required. |
| `["matches", compound]` | keep `e` iff `e.matches(compound)` (a CSS compound written directly after an operator, e.g. `:upward(2).foo`, `:has-text(x):not(.y)`). |
| `["has", chain]` | keep `e` iff evaluating `chain` with root `e` yields >= 1 element. In a `has` sub-chain the first task is normally `["css", s]` evaluated **relative to `e`**: `s` starting with `"> "` -> `e.querySelectorAll(":scope " + s)`; starting with `"+ "` / `"~ "` -> sibling form as in `spath`; otherwise `e.querySelectorAll(s)` (`s` may contain `:scope`). Subsequent tasks as usual. A `has` sub-chain may also start with an operator (e.g. `:has(:has-text(x))`): then the starting set is all descendants of `e` (`e.querySelectorAll("*")`). |
| `["not", chain]` | keep `e` iff evaluating `chain` on the singleton set `[e]` yields nothing. The sub-chain never starts with `css`; a leading CSS compound is emitted as `["matches", c]`. A leading combinator form (`:not(> a)`) is emitted as `["has", [["css","> a"]]]` inside it. |
| `["has-text", pat]` | keep `e` iff `pattern(pat).test(e.textContent)` |
| `["min-text-length", n]` | keep `e` iff `e.textContent.length >= n` (n: int) |
| `["matches-attr", namePat, valuePat_or_null]` | keep `e` iff some attribute name matches `namePat` and (valuePat null or its value matches). Literals are already converted to anchored regexes by the compiler (`*` = wildcard). |
| `["matches-css", pseudo_or_null, prop, pat]` | `pseudo` is `null`, `"before"` or `"after"`; keep `e` iff `getComputedStyle(e, pseudo ? "::" + pseudo : null).getPropertyValue(prop)` matches `pat` |
| `["matches-media", query]` | pass-through iff `matchMedia(query).matches`, else empty set (re-evaluate on `change`) |
| `["matches-path", pat]` | gate: pass-through iff `pattern(pat).test(location.pathname + location.search)`, else empty. May appear while the set is still `null` (then it just gates). |
| `["matches-prop", chain, pat_or_null]` | keep `e` iff property chain `a.b.c` exists on `e` (and `String(value)` matches pat) |
| `["others"]` | everything except the input elements, their ancestors and descendants (excluding head subtree) |
| `["upward", n]` | n int 1..255: n-th `parentElement` of each `e` |
| `["upward", sel]` | sel string: `e.parentElement && e.parentElement.closest(sel)` |
| `["watch-attr", [names]]` | pass-through; names = [] means any attribute. Engine also re-runs the filter on attribute mutations (of those names). |
| `["xpath", expr]` | set `null` -> evaluate on `document`; else with each `e` as context node; ORDERED_NODE_SNAPSHOT_TYPE, keep elements |

Gate tasks (`matches-path`, `matches-media`, `watch-attr`) may appear while the set is still `null`;
`xpath` may start a chain. If the selector starts with any other operator (e.g. `##:has-text(x)`),
the compiler inserts `["css", "*"]` first. A leading negated gate (`:not(:matches-path(/x/)) .ad`) is
rooted at `<html>`: `[["css","html"], ["not", [["matches-path", ...]]], ["spath", " .ad"]]` (no new task
type; a bare negated gate with nothing after it is rejected by the compiler).

### Patterns (`pat`)

```json
{"r": "<regex source>", "f": "<flags>"}   // JS RegExp(source, flags); flags subset of "imsu"
{"t": "<literal>"}                         // plain case-sensitive substring test (text.includes)
```

`has-text("")` -> `{"t": ""}` (matches everything).

## Actions (`"a"`)

| action | meaning |
|---|---|
| absent | hide (`display:none!important` via random attribute + stylesheet rule) |
| `["style", decl]` | apply sanitized declarations (no `url(`, `image-set(`, `@import`, `expression`, `\\`, `/*`, `//`, `{`, `}`) |
| `["remove"]` | `node.remove()`, keep removing re-inserted matches |
| `["remove-attr", pat]` | remove attributes whose name matches `pat` (literal = exact name: compiler emits `{"r": "^name$", "f": ""}`) |
| `["remove-class", pat]` | remove classes matching `pat` (literal = exact class: same anchoring) |

Plain-CSS selectors with `:style()` / `:remove()` are **not** proc: they go to site.db `"style"` / `"remove"`.
Plain-CSS selectors with `:remove-attr()` / `:remove-class()` / `:matches-media()` / `:matches-path()` /
`:watch-attr()` become proc entries (e.g. `{"s": "a[onclick]:remove-attr(onclick)", "t": [["css","a[onclick]"]], "a": ["remove-attr", {"r":"^onclick$","f":""}]}`).

## Exceptions (`#@#`)

`site.db` `"unhide"` lists hold the raw selector text after `#@#` (trimmed). It cancels:
- `hide` entry `sel` when text == `sel`
- `style` entry `[sel, decl]` when text == `sel + ":style(" + decl + ")"`
- `remove` entry `sel` when text == `sel + ":remove()"`
- `proc` entry when text == entry `"s"`

`s` is the selector text as written in the list (after AdGuard alias spellings were kept, i.e. the
raw text), so exceptions must be written with the same spelling (uBO behaves the same way).

## Example

`example.com##div.ad:has-text(/Sponsored/i):upward(2)` ->

```json
{"s": "div.ad:has-text(/Sponsored/i):upward(2)",
 "t": [["css", "div.ad"], ["has-text", {"r": "Sponsored", "f": "i"}], ["upward", 2]]}
```

`twitter.com##:matches-path(/^/home/) [data-testid="primaryColumn"]:others()` ->

```json
{"s": ":matches-path(/^/home/) [data-testid=\"primaryColumn\"]:others()",
 "t": [["matches-path", {"r": "^/home", "f": ""}], ["css", "[data-testid=\"primaryColumn\"]"], ["others"]]}
```

`x.com##div:has(> span:has-text(Ad))` ->

```json
{"s": "div:has(> span:has-text(Ad))",
 "t": [["css", "div"], ["has", [["css", "> span"], ["has-text", {"t": "Ad"}]]]]}
```
