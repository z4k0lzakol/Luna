(function () {
    'use strict';
    var noop = function () {};
    window.cxApi = {
        ORIGINAL_VARIATION: 0,
        NO_CHOSEN_VARIATION: -1,
        NOT_PARTICIPATING: -2,
        chooseVariation: function () { return 0; },
        getChosenVariation: function () { return 0; },
        setChosenVariation: noop,
        setDomainName: noop,
        setCookiePath: noop,
        setAllowHash: noop
    };
})();
