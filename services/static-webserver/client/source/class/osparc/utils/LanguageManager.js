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

    // the backend supports the following locales
    __localeMapping: {
      "en_US": "en",
      "es_ES": "es_ES",
      "zh": "zh_CN",
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

    setLocale: function(localeCode) {
      if (!this.getAvailableLocales().includes(localeCode)) {
        return;
      }
      qx.locale.Manager.getInstance().setLocale(localeCode);
      qx.event.message.Bus.getInstance().dispatchByName("localeSwitch", localeCode);
    },

    getUserLocale: function() {
      return qx.locale.Manager.getInstance().getLocale();
    },

    patchLocale: function(localeCode) {
      const params = {
        data: {
          "language": this.__localeMapping[localeCode],
        },
      };
      return osparc.data.Resources.fetch("profile", "patch", params)
        .catch(err => osparc.FlashMessenger.logError(err, qx.locale.Manager.tr("Unsuccessful language update")));
    },

    /**
     * Applies the user's locale (if any and still available).
     * Meant to be called early during application startup.
     */
    applyUsersLocale: function(userLocale) {
      if (!userLocale) {
        userLocale = this.__getBrowserLocale();
      }
      this.setLocale(userLocale);
    },

    /**
     * Resolves the best available locale for the user's browser language,
     * falling back to English ("en_US") when there is no match.
     * @return {String} e.g. "es_ES"
     */
    __getBrowserLocale: function() {
      const available = this.getAvailableLocales();
      const fallback = available.includes("en_US") ? "en_US" : available[0];

      const language = qx.bom.client.Locale.getLocale(); // e.g. "es"
      if (!language) {
        return fallback;
      }
      const region = qx.bom.client.Locale.getVariant(); // e.g. "ES"
      const full = region ? `${language}_${region}` : language; // e.g. "es_ES"
      // exact match (e.g. "es_ES") or language-only match (e.g. "zh")
      if (available.includes(full)) {
        return full;
      }
      if (available.includes(language)) {
        return language;
      }
      // match by language prefix (e.g. "es" -> "es_ES")
      const byPrefix = available.find(localeCode => localeCode.split("_")[0] === language);
      return byPrefix || fallback;
    },
  }
});
