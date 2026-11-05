(function () {
    'use strict';
    var w = window;
    var noop = function () {};
    var id = '';
    for (var i = 0; i < 16; i++) { id += Math.floor(Math.random() * 16).toString(16); }
    var s = {
        para: {},
        getPresetProperties: function () { return {}; },
        getDistinctId: function () { return id; },
        track: function (ev, props, cb) {
            var f = typeof props === 'function' ? props : cb;
            if (typeof f === 'function') { setTimeout(function () { try { f(); } catch (e) {} }, 0); }
        }
    };
    ['init', 'quick', 'trackLink', 'trackLinks', 'login', 'logout', 'identify', 'register', 'registerPage',
        'clearAllRegister', 'setProfile', 'setOnceProfile', 'appendProfile', 'incrementProfile',
        'deleteProfile', 'unsetProfile', 'use', 'bind', 'setPara', 'trackSignup', 'registerPlugin',
        'getAnonymousID', 'resetAnonymousIdentity'].forEach(function (n) { s[n] = noop; });
    s.getAnonymousID = function () { return id; };
    var prev = w.sensorsDataAnalytic201505;
    w.sensorsDataAnalytic201505 = s;
    if (typeof prev === 'string' && /^[A-Za-z_$][\w$]*$/.test(prev)) {
        var cur = w[prev];
        var q = cur && Array.isArray(cur._q) ? cur._q : [];
        w[prev] = s;
        for (var j = 0; j < q.length; j++) {
            var e = q[j];
            if (e && typeof s[e[0]] === 'function') { try { s[e[0]].apply(s, Array.prototype.slice.call(e[1] || [])); } catch (x) {} }
        }
    }
})();
