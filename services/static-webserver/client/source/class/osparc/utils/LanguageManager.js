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
    // Locale registry keyed by qooxdoo compiler locale
    __locales: {
      "en_US": {
        backend: "en",
        label: "English",
      },
      "es_ES": {
        backend: "es_ES",
        label: "Español [Spanish]",
      },
      "zh": {
        backend: "zh_CN",
        label: "中文 [Chinese]",
      },
    },

    /**
     * Maps a qooxdoo (frontend) locale to the backend's SupportedLocale.
     * @return {String} e.g. "en_US" -> "en"
     */
    __toBackendLocale: function(frontendLocale) {
      const locale = this.__locales[frontendLocale];
      return locale ? locale.backend : frontendLocale;
    },

    /**
     * Maps a backend SupportedLocale to the qooxdoo (frontend) locale.
     * @return {String} e.g. "en" -> "en_US"
     */
    __toFrontendLocale: function(backendLocale) {
      const frontendLocale = Object.keys(this.__locales)
        .find(feLocale => this.__locales[feLocale].backend === backendLocale);
      return frontendLocale || backendLocale;
    },

    /**
     * Works around a qooxdoo compiler CLDR-extraction issue where some locale
     * entries (e.g. the Chinese number separators) end up as objects
     * ({"_": ".", "$": {"draft": "contributed"}}) instead of plain strings.
     * Such values break locale-dependent widgets: qx.ui.form.Spinner builds its
     * text field's filter RegExp from the decimal/group separators and throws
     * ("Exception while creating child control 'textfield'") when they are not
     * strings.
     * Flattens any object-valued locale entry to its "_" string.
     * Meant to be called once, early during application startup.
     * Common Locale Data Repository (CLDR) - https://cldr.unicode.org/
     */
    normalizeCldrData: function() {
      // eslint-disable-next-line no-underscore-dangle
      const catalog = qx.locale.Manager.getInstance().__locales;
      if (!catalog) {
        return;
      }
      Object.keys(catalog).forEach(localeCode => {
        const localeMap = catalog[localeCode];
        if (!localeMap || typeof localeMap !== "object") {
          return;
        }
        Object.keys(localeMap).forEach(key => {
          const value = localeMap[key];
          if (value && typeof value === "object" && typeof value["_"] === "string") {
            localeMap[key] = value["_"];
          }
        });
      });
    },

    /**
     * Returns the locales for which translations were compiled (see compile.json).
     * @return {String[]} e.g. ["en_US", "es_ES"]
     */
    getAvailableLocales: function() {
      return qx.locale.Manager.getInstance().getAvailableLocales();
    },

    getLocaleLabel: function(localeCode) {
      const locale = this.__locales[localeCode];
      return locale ? locale.label : localeCode;
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
      if (!osparc.data.Permissions.getInstance().canDo("user.user.update", true)) {
        return Promise.resolve();
      }
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
