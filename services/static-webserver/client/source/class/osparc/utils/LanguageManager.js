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

    // maps qooxdoo compiler locales (keys) to backend SupportedLocale values
    __localeMapping: {
      "en_US": "en",
      "es_ES": "es_ES",
      "zh": "zh_CN",
    },

    /**
     * Maps a qooxdoo (frontend) locale to the backend's SupportedLocale.
     * @return {String} e.g. "en_US" -> "en"
     */
    __toBackendLocale: function(frontendLocale) {
      return this.__localeMapping[frontendLocale] || frontendLocale;
    },

    /**
     * Maps a backend SupportedLocale to the qooxdoo (frontend) locale.
     * @return {String} e.g. "en" -> "en_US"
     */
    __toFrontendLocale: function(backendLocale) {
      const frontendLocale = Object.keys(this.__localeMapping).find(feLocale => this.__localeMapping[feLocale] === backendLocale);
      return frontendLocale || backendLocale;
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

    /**
     * Activates a locale and broadcasts the change.
     * @return {Boolean} true if the locale was available and applied, false otherwise.
     */
    setLocale: function(localeCode) {
      if (!this.getAvailableLocales().includes(localeCode)) {
        console.warn(`Locale "${localeCode}" is not available; keeping current locale.`);
        return false;
      }
      qx.locale.Manager.getInstance().setLocale(localeCode);
      qx.event.message.Bus.getInstance().dispatchByName("localeSwitch", localeCode);
      return true;
    },

    getUserLocale: function() {
      return qx.locale.Manager.getInstance().getLocale();
    },

    /**
     * Returns the current locale in the backend's SupportedLocale form (for API headers/requests).
     * @return {String} e.g. "en", "zh_CN"
     */
    getBackendLocale: function() {
      return this.__toBackendLocale(this.getUserLocale());
    },

    patchLocale: function(localeCode) {
      const params = {
        data: {
          "language": this.__toBackendLocale(localeCode),
        },
      };
      return osparc.data.Resources.fetch("profile", "patch", params)
        .catch(err => osparc.FlashMessenger.logError(err, qx.locale.Manager.tr("Unsuccessful language update")));
    },

    /**
     * Applies the user's locale (if any and still available).
     * @param {String} [userLocale] backend SupportedLocale (e.g. "en", "zh_CN"); falls back to the browser locale when empty or unresolvable.
     * Meant to be called early during application startup.
     */
    applyUsersLocale: function(userLocale) {
      const frontendLocale = userLocale ? this.__toFrontendLocale(userLocale) : null;
      // fall back to the browser locale when there is no persisted choice or it cannot be applied
      if (!frontendLocale || !this.setLocale(frontendLocale)) {
        this.setLocale(this.__getBrowserLocale());
      }
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
