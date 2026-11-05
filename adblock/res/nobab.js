(function () {
    'use strict';
    var w = window;
    var d = document;
    var nativeEval = w.eval;
    var nativeSetTimeout = w.setTimeout;
    var loader = ['ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', 'String.fromCharCode',
        'DOMContentLoaded', 'doScroll', 'clientWidth'];
    var isBab = function (s) {
        if (typeof s !== 'string' || s.length < 20) { return false; }
        if (/blockadblock|babasbm|bab_elementid/i.test(s)) { return true; }
        if (s.indexOf('babn') >= 0 && s.indexOf('getItem') >= 0) { return true; }
        for (var i = 0; i < loader.length; i++) { if (s.indexOf(loader[i]) < 0) { return false; } }
        return s.indexOf('sessionStorage') >= 0 || s.indexOf('localStorage') >= 0 || s.indexOf('Math.random') >= 0;
    };
    var undo = function () {
        var b = d.body;
        if (b && b.style && b.style.visibility) { b.style.removeProperty('visibility'); }
        var nodes = d.querySelectorAll('[id^="babasbm"]');
        for (var i = 0; i < nodes.length; i++) { nodes[i].remove(); }
    };
    var tidy = function () {
        undo();
        nativeSetTimeout.call(w, undo, 500);
    };
    var defused = false;
    w.eval = new Proxy(nativeEval, {
        apply: function (t, self, args) {
            var s = args[0];
            if (isBab(s)) {
                if (!defused) {
                    defused = true;
                    if (d.readyState === 'loading') { d.addEventListener('DOMContentLoaded', tidy, { once: true }); }
                    else { tidy(); }
                }
                return undefined;
            }
            return Reflect.apply(t, self, args);
        }
    });
    w.setTimeout = new Proxy(nativeSetTimeout, {
        apply: function (t, self, args) {
            var a = args[0];
            if (typeof a === 'string' && /\.bab_elementid.$/.test(a)) { return 0; }
            return Reflect.apply(t, self, args);
        }
    });
})();
