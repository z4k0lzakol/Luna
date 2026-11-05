(function () {
    'use strict';
    var d = document;
    var clean = function () {
        var list = d.querySelectorAll('style[amp-boilerplate]');
        for (var i = 0; i < list.length; i++) { list[i].remove(); }
        var ns = d.querySelectorAll('noscript');
        for (var j = 0; j < ns.length; j++) {
            if (/amp-boilerplate/.test(ns[j].textContent || '')) { ns[j].remove(); }
        }
        if (d.body && d.body.style.animation) { d.body.style.animation = 'none'; }
    };
    clean();
    if (d.readyState === 'loading') { d.addEventListener('DOMContentLoaded', clean, { once: true }); }
})();
