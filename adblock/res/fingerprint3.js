(function () {
    'use strict';
    var w = window;
    var id = '';
    for (var i = 0; i < 32; i++) { id += Math.floor(Math.random() * 16).toString(16); }
    var agent = {
        get: function () {
            return Promise.resolve({
                visitorId: id,
                confidence: { score: 0.5 },
                components: {},
                version: '3.4.2'
            });
        }
    };
    w.FingerprintJS = {
        load: function () { return Promise.resolve(agent); },
        hashComponents: function () { return id; },
        componentsToDebugString: function () { return '{}'; }
    };
})();
