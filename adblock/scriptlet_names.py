# Scriptlet name tables shared by the compiler (subprocess) and scriptlets.py (GUI process).
# Source: Luna scriptlet spec registry.json (clean-room, built from uBO/AdGuard docs + filter-list census).
#
# ALIASES      {alias: canonical}            - only real aliases (canonical names are not keys)
# KNOWN        {canonical}                   - every name the lists may use (supported or not)
# TRUSTED_ONLY {canonical and alias names}   - honoured only from trusted lists
# SUPPORTED    {canonical}                   - names with an implementation in adblock/js/scriptlets/<name>.js
#                                              (each builder agent owns one marked block below)
# canonical(name) -> canonical name or None  - strips ".js", AdGuard "ubo-" prefix, resolves aliases

ALIASES = {
    "abort-current-inline-script": "abort-current-script",
    "acis": "abort-current-script",
    "acs": "abort-current-script",
    "aopr": "abort-on-property-read",
    "aopw": "abort-on-property-write",
    "aost": "abort-on-stack-trace",
    "aeld": "addEventListener-defuser",
    "prevent-addEventListener": "addEventListener-defuser",
    "nano-setInterval-booster": "adjust-setInterval",
    "nano-sib": "adjust-setInterval",
    "nano-setTimeout-booster": "adjust-setTimeout",
    "nano-stb": "adjust-setTimeout",
    "window-close-if": "close-window",
    "fingerprintjs2": "fingerprint2",
    "fingerprintjs3": "fingerprint3",
    "google-ima3": "google-ima",
    "bab-defuser": "nobab",
    "prevent-bab": "nobab",
    "prevent-bab2": "nobab2",
    "prevent-eval-if": "noeval-if",
    "silent-noeval": "noeval-silent",
    "fuckadblock.js-3.2.0": "nofab",
    "prevent-fab-3.2.0": "nofab",
    "popads.net": "popads",
    "prevent-popads-net": "popads",
    "set-popads-dummy": "popads-dummy",
    "no-fetch-if": "prevent-fetch",
    "refresh-defuser": "prevent-refresh",
    "no-requestAnimationFrame-if": "prevent-requestAnimationFrame",
    "norafif": "prevent-requestAnimationFrame",
    "no-setInterval-if": "prevent-setInterval",
    "nosiif": "prevent-setInterval",
    "setInterval-defuser": "prevent-setInterval",
    "no-setTimeout-if": "prevent-setTimeout",
    "nostif": "prevent-setTimeout",
    "setTimeout-defuser": "prevent-setTimeout",
    "no-window-open-if": "prevent-window-open",
    "nowoif": "prevent-window-open",
    "window.open-defuser": "prevent-window-open",
    "no-xhr-if": "prevent-xhr",
    "ra": "remove-attr",
    "rc": "remove-class",
    "cookie-remover": "remove-cookie",
    "rmnt": "remove-node-text",
    "set": "set-constant",
    "trusted-create-HTML": "trusted-create-html",
    "trusted-rpfr": "trusted-replace-fetch-response",
    "replace-node-text": "trusted-replace-node-text",
    "rpnt": "trusted-replace-node-text",
    "trusted-rpnt": "trusted-replace-node-text",
    "trusted-rpot": "trusted-replace-outbound-text",
    "trusted-set": "trusted-set-constant",
}

KNOWN = {
    "abort-current-script", "abort-on-property-read", "abort-on-property-write", "abort-on-stack-trace",
    "addEventListener-defuser", "addEventListener-logger", "adjust-setInterval", "adjust-setTimeout", "aell",
    "alert-buster", "ampproject_v0", "call-nothrow", "close-window", "csp", "disable-newtab-links",
    "edit-element-object", "edit-inbound-object", "edit-object-on-getter", "edit-object-on-setter",
    "edit-outbound-object", "edit-this-object", "evaldata-prune", "fingerprint2", "fingerprint3",
    "freeze-element-property", "golem.de", "google-ima", "href-sanitizer", "json-edit", "json-edit-fetch-request",
    "json-edit-fetch-response", "json-edit-xhr-request", "json-edit-xhr-response", "json-prune",
    "json-prune-fetch-response", "json-prune-xhr-response", "jsonl-edit-fetch-response", "jsonl-edit-xhr-response",
    "jsonl-prune-fetch-response", "jsonl-prune-xhr-response", "m3u-prune", "multiup", "no-floc", "nobab", "nobab2",
    "noeval", "noeval-if", "noeval-silent", "nofab", "nowebrtc", "overlay-buster", "popads", "popads-dummy",
    "prebid-ads", "prevent-canvas", "prevent-clipboard-write", "prevent-dialog", "prevent-fetch",
    "prevent-innerHTML", "prevent-navigation", "prevent-refresh", "prevent-requestAnimationFrame",
    "prevent-setInterval", "prevent-setTimeout", "prevent-window-open", "prevent-xhr", "proxy-apply-config",
    "remove-attr", "remove-cache-storage-item", "remove-class", "remove-cookie", "remove-node-text", "set-attr",
    "set-constant", "set-cookie", "set-cookie-reload", "set-local-storage-item", "set-session-storage-item",
    "sharedWorker-defuser", "spoof-css", "trusted-click-element", "trusted-create-html",
    "trusted-edit-element-object", "trusted-edit-inbound-object", "trusted-edit-object-on-getter",
    "trusted-edit-object-on-setter", "trusted-edit-outbound-object", "trusted-edit-this-object",
    "trusted-json-edit", "trusted-json-edit-fetch-request", "trusted-json-edit-fetch-response",
    "trusted-json-edit-xhr-request", "trusted-json-edit-xhr-response", "trusted-jsonl-edit-fetch-response",
    "trusted-jsonl-edit-xhr-response", "trusted-override-element-method", "trusted-prevent-dom-bypass",
    "trusted-prevent-fetch", "trusted-prevent-xhr", "trusted-prune-inbound-object", "trusted-prune-outbound-object",
    "trusted-replace-argument", "trusted-replace-fetch-response", "trusted-replace-node-text",
    "trusted-replace-outbound-text", "trusted-replace-xhr-response", "trusted-set-attr", "trusted-set-constant",
    "trusted-set-cookie", "trusted-set-cookie-reload", "trusted-set-local-storage-item",
    "trusted-set-session-storage-item", "trusted-suppress-native-method", "webrtc-if", "window.name-defuser",
    "xml-prune",
}

# every canonical "trusted-*" name plus every alias that resolves to one (rpnt, replace-node-text, trusted-set, ...)
TRUSTED_ONLY = {n for n in KNOWN if n.startswith("trusted-")}
TRUSTED_ONLY |= {a for a, c in ALIASES.items() if c in TRUSTED_ONLY}

SUPPORTED = set()
# --- RUNTIME ---
SUPPORTED |= {
    "set-constant", "abort-on-property-read", "abort-on-property-write", "abort-current-script",
    "abort-on-stack-trace", "prevent-setTimeout", "prevent-setInterval", "adjust-setTimeout",
    "adjust-setInterval", "addEventListener-defuser", "prevent-window-open", "remove-node-text",
}
# --- /RUNTIME ---
# --- SCRIPTLETS-1 ---
# (internal helpers lib-json.js / lib-net.js are deps only, not list names)
SUPPORTED |= {
    "prevent-fetch", "trusted-prevent-fetch", "prevent-xhr", "trusted-prevent-xhr",
    "json-prune", "json-prune-fetch-response", "json-prune-xhr-response",
    "jsonl-prune-fetch-response", "jsonl-prune-xhr-response",
    "trusted-replace-fetch-response", "trusted-replace-xhr-response",
    "trusted-prune-inbound-object", "trusted-prune-outbound-object",
    "json-edit", "trusted-json-edit", "json-edit-fetch-response", "json-edit-xhr-response",
    "json-edit-fetch-request", "json-edit-xhr-request", "jsonl-edit-fetch-response", "jsonl-edit-xhr-response",
    "trusted-json-edit-fetch-response", "trusted-json-edit-xhr-response", "trusted-json-edit-fetch-request",
    "trusted-json-edit-xhr-request", "trusted-jsonl-edit-fetch-response", "trusted-jsonl-edit-xhr-response",
    "edit-outbound-object", "edit-inbound-object", "edit-this-object", "edit-element-object",
    "edit-object-on-setter", "edit-object-on-getter", "trusted-edit-outbound-object", "trusted-edit-inbound-object",
    "trusted-edit-this-object", "trusted-edit-element-object", "trusted-edit-object-on-setter",
    "trusted-edit-object-on-getter", "xml-prune", "m3u-prune", "noeval", "noeval-silent", "noeval-if",
    "evaldata-prune", "nowebrtc",
}
# --- /SCRIPTLETS-1 ---
# --- SCRIPTLETS-2 ---
SUPPORTED |= {
    "remove-attr", "remove-class", "set-attr", "trusted-set-attr", "trusted-replace-node-text",
    "set-cookie", "set-cookie-reload", "trusted-set-cookie", "trusted-set-cookie-reload", "remove-cookie",
    "set-local-storage-item", "set-session-storage-item", "trusted-set-local-storage-item",
    "trusted-set-session-storage-item", "href-sanitizer", "trusted-click-element", "prevent-innerHTML",
    "spoof-css", "close-window", "disable-newtab-links", "prevent-refresh", "prevent-requestAnimationFrame",
    "prevent-canvas", "call-nothrow", "trusted-replace-argument", "trusted-prevent-dom-bypass",
    "trusted-create-html",
}
# --- /SCRIPTLETS-2 ---
# --- SCRIPTLETS-3 ---
SUPPORTED |= {
    "alert-buster", "window.name-defuser", "trusted-set-constant", "trusted-suppress-native-method",
    "trusted-override-element-method", "trusted-replace-outbound-text", "prevent-navigation", "overlay-buster",
    "prevent-dialog", "webrtc-if", "prevent-clipboard-write", "proxy-apply-config", "remove-cache-storage-item",
    "freeze-element-property", "multiup", "nofab", "nobab", "nobab2", "popads", "popads-dummy", "prebid-ads",
    "fingerprint2", "fingerprint3", "google-ima", "ampproject_v0",
    # removed/deprecated uBO names: accepted, inert (spec 03c 15)
    "aell", "addEventListener-logger", "golem.de", "no-floc", "csp", "sharedWorker-defuser",
}
# --- /SCRIPTLETS-3 ---


def canonical(name):
    """'nostif.js' -> 'prevent-setTimeout'; 'ubo-aopr' -> 'abort-on-property-read'; unknown -> None."""
    if not isinstance(name, str):
        return None
    n = name.strip()
    if n.startswith("ubo-"):
        n = n[4:]
    if n in KNOWN or n in ALIASES:
        return ALIASES.get(n, n)
    if n.endswith(".js"):
        n2 = n[:-3]
        if n2 in KNOWN or n2 in ALIASES:
            return ALIASES.get(n2, n2)
    return None


def is_trusted_only(name):
    c = canonical(name)
    return name in TRUSTED_ONLY or (c is not None and c in TRUSTED_ONLY)
