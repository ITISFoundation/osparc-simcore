/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2026 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Helper to manage the application's locale.
 */

qx.Class.define("osparc.utils.LanguageManager", {
  type: "static",

  statics: {
    // Display names for the locales we want to expose
    __localeLabels: {
      "en_US": "English",
      "es_ES": "Español [Spanish]",
      "zh": "中文 [Chinese]",
    },

    /**
     * Returns the locales for which translations were compiled (see compile.json).
     * @return {String[]} e.g. ["en_US", "es_ES"]
     */
    getAvailableLocales: function() {
      return qx.locale.Manager.getInstance().getAvailableLocales();
    },

    getLocaleLabel: function(localeCode) {
      return this.__localeLabels[localeCode] || localeCode;
    },

    isSwitchUseful: function() {
      return this.getAvailableLocales().length > 1;
    },

    getStoredLocale: function() {
      return osparc.Preferences.getInstance().getUserLocale();
    },

    applyLocale: function(localeCode) {
      if (localeCode && this.getAvailableLocales().includes(localeCode)) {
        qx.locale.Manager.getInstance().setLocale(localeCode);
      }
    },

    setLocale: function(localeCode) {
      if (!this.getAvailableLocales().includes(localeCode)) {
        return;
      }
      osparc.Preferences.getInstance().setUserLocale(localeCode);
    }
  }
});
