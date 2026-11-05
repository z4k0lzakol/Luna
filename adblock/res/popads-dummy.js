(function () {
    'use strict';
    var w = window;
    var dummy = {};
    ['PopAds', 'popns'].forEach(function (name) {
        try {
            Object.defineProperty(w, name, {
                get: function () { return dummy; },
                set: function () {},
                configurable: false
            });
        } catch (e) {}
    });
})();
