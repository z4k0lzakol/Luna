(function () {
    'use strict';
    var w = window;
    var magic = String.fromCharCode(Date.now() % 26 + 97) + Math.floor(Math.random() * 982451653 + 982451653).toString(36);
    var trap = function (name) {
        try {
            Object.defineProperty(w, name, {
                get: function () { return undefined; },
                set: function () { throw new ReferenceError(magic); },
                configurable: true
            });
        } catch (e) {}
    };
    trap('PopAds');
    trap('popns');
})();
