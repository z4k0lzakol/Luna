(function () {
    'use strict';
    var w = window;
    var c = w.COMSCORE;
    if (c === null || typeof c !== 'object') { c = {}; }
    c.beacon = function () {};
    c.purge = function () { w._comscore = []; };
    w.COMSCORE = c;
    if (Array.isArray(w._comscore)) { w._comscore.length = 0; }
})();
