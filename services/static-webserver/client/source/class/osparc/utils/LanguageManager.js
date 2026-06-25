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
    LOCALE_KEY: "osparc.locale",

    // Display names for the locales we want to expose
    __localeLabels: {
      "en_US": "English",
      "es_ES": "Español [Spanish]",
      "zh_CN": "中文 [Chinese]",
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
      return osparc.utils.Utils.localCache.getLocalStorageItem(this.LOCALE_KEY);
    },

    setLocale: function(localeCode) {
      if (!this.getAvailableLocales().includes(localeCode)) {
        return;
      }
      osparc.utils.Utils.localCache.setLocalStorageItem(this.LOCALE_KEY, localeCode);
      qx.locale.Manager.getInstance().setLocale(localeCode);
    },

    /**
     * Applies the locale stored in localStorage (if any and still available).
     * Meant to be called early during application startup.
     */
    applyStoredLocale: function() {
      const storedLocale = this.getStoredLocale();
      if (storedLocale && this.getAvailableLocales().includes(storedLocale)) {
        qx.locale.Manager.getInstance().setLocale(storedLocale);
      }
    }
  }
});
