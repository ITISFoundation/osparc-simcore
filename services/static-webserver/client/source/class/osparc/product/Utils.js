/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Sandbox of static methods related to products.
 */

qx.Class.define("osparc.product.Utils", {
  type: "static",

  statics: {
    getProductName: function() {
      return qx.core.Environment.get("product.name");
    },

    isProduct: function(productName) {
      const product = this.getProductName();
      return (productName === product);
    },

    isS4LProduct: function() {
      return (
        this.isProduct("s4l") ||
        this.isProduct("s4lacad") ||
        this.isProduct("s4ldesktop") ||
        this.isProduct("s4ldesktopacad")
      );
    },

    getStudyAlias: function(options = {}) {
      let alias = null;
      if (options.plural) {
        alias = qx.locale.Manager.tr("projects");
      } else {
        alias = qx.locale.Manager.tr("project");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    getTemplateAlias: function(options = {}) {
      let alias = null;
      if (options.plural) {
        alias = qx.locale.Manager.tr("templates");
      } else {
        alias = qx.locale.Manager.tr("template");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    getTutorialAlias: function(options = {}) {
      let alias = qx.locale.Manager.tr("tutorial");
      if (options.plural) {
        alias = qx.locale.Manager.tr("tutorials");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    getHypertoolAlias: function(options = {}) {
      let alias = qx.locale.Manager.tr("hypertool");
      if (options.plural) {
        alias = qx.locale.Manager.tr("hypertools");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    getServiceAlias: function(options = {}) {
      let alias = qx.locale.Manager.tr("service");
      if (options.plural) {
        alias = qx.locale.Manager.tr("services");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    getAppAlias: function(options = {}) {
      let alias = qx.locale.Manager.tr("app");
      if (options.plural) {
        alias = qx.locale.Manager.tr("Apps");
      }

      if (options.firstUpperCase) {
        alias = osparc.utils.Utils.capitalize(alias);
      } else if (options.allUpperCase) {
        alias = alias.toUpperCase();
      }

      return alias;
    },

    resourceTypeToAlias: function(resourceType, options) {
      switch (resourceType) {
        case "study":
          return this.getStudyAlias(options);
        case "template":
          return this.getTemplateAlias(options);
        case "tutorial":
          return this.getTutorialAlias(options);
        case "service":
          // return this.getServiceAlias(options);
          // Do not use this alias anymore, use "app" instead
          return this.getAppAlias(options);
        case "hypertool":
          return this.getHypertoolAlias(options);
        case "app":
          return this.getAppAlias(options);
      }
      return resourceType;
    },

    getLogoPath: function(longLogo = true) {
      let logosPath = null;
      const colorManager = qx.theme.manager.Color.getInstance();
      const textColor = colorManager.resolve("text");
      const lightLogo = osparc.utils.Utils.getColorLuminance(textColor) > 0.4;
      const product = osparc.product.Utils.getProductName();
      switch (product) {
        case "s4l": {
          if (lightLogo) {
            if (longLogo) {
              logosPath = "osparc/Sim4Life_full_logo_white.svg";
            } else {
              logosPath = "osparc/s4l_logo_white_short.svg";
            }
          } else if (longLogo) {
            logosPath = "osparc/Sim4Life_full_logo_black.svg";
          } else {
            logosPath = "osparc/s4l_logo_black_short.svg";
          }
          break;
        }
        case "s4llite":
          logosPath = lightLogo ? "osparc/s4llite-white.png" : "osparc/s4llite-black.png";
          break;
        case "s4lacad":
          logosPath = lightLogo ? "osparc/Sim4Life_full_logo_white.svg" : "osparc/Sim4Life_full_logo_black.svg";
          break;
        case "s4ldesktop":
          logosPath = lightLogo ? "osparc/Sim4Life_full_logo_white.svg" : "osparc/Sim4Life_full_logo_black.svg";
          break;
        case "s4ldesktopacad":
          logosPath = lightLogo ? "osparc/Sim4Life_full_logo_white.svg" : "osparc/Sim4Life_full_logo_black.svg";
          break;
        case "tis":
          logosPath = lightLogo ? "osparc/tip_itis-white.svg" : "osparc/tip_itis-black.svg";
          break;
        case "tiplite":
          logosPath = lightLogo ? "osparc/tip_lite_itis-white.svg" : "osparc/tip_lite_itis-black.svg";
          break;
        default:
          logosPath = lightLogo ? "osparc/osparc-white.svg" : "osparc/osparc-black.svg";
          break;
      }
      return logosPath;
    },

    forceNullCreditsColor: function(wallet) {
      // TIP is a product that can be used for free, so allow making 0 credits scenario more friendly.
      if (osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("tiplite")) {
        // Ideally, check if there was ever a transaction. If not, keep the indicator gray.
        // Note: Since we can't fetch payments per wallet, for now rely on the available credits.
        const credits = wallet.getCreditsAvailable();
        return credits === 0;
      }
      return false;
    },

    /**
     * @returns {String} ["REGISTER", "REQUEST_ACCOUNT_FORM", "REQUEST_ACCOUNT_INSTRUCTIONS"]
     */
    getCreateAccountAction: function() {
      const config = osparc.store.Store.getInstance().get("config");
      if (config["invitation_required"]) {
        const vendor = osparc.store.VendorInfo.getInstance().getVendor();
        if (vendor["invitation_form"]) {
          // If invitation_required (login_settings) and invitation_form (vendor)
          return "REQUEST_ACCOUNT_FORM";
        }
        // do not show request account form, pop up a dialog with instructions instead
        return "REQUEST_ACCOUNT_INSTRUCTIONS";
      }
      return "REGISTER";
    },

    // oSPARC only
    showExportCMis: function() {
      const product = this.getProductName();
      return product === "osparc";
    },

    // All products except oSPARC
    hasIdlingTrackerEnabled: function() {
      const product = this.getProductName();
      return product !== "osparc";
    },

    // All products except oSPARC
    showLicenseExtra: function() {
      const product = this.getProductName();
      return product !== "osparc";
    },

    showStudyPreview: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    showAboutProduct: function() {
      return (
        this.isS4LProduct() ||
        this.isProduct("s4llite") ||
        this.isProduct("tis") ||
        this.isProduct("tiplite")
      );
    },

    showPreferencesTokens: function() {
      if (osparc.data.Permissions.getInstance().isTester()) {
        return true;
      }

      if (this.isProduct("s4llite") || this.isProduct("tis") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    showPreferencesExperimental: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    showDisableServiceAutoStart: function() {
      if (this.isProduct("s4llite")) {
        return false;
      }
      return true;
    },

    showTemplates: function() {
      if (osparc.data.Permissions.getInstance().isTester()) {
        return true;
      }

      if (this.isProduct("tis") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    showPublicProjects: function() {
      if (osparc.data.Permissions.getInstance().isTester()) {
        return true;
      }

      if (this.isProduct("tis") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    showFunctions: function() {
      if (!osparc.data.Permissions.getInstance().checkFunctionPermissions("readFunctions")) {
        return false;
      }

      return [
        "osparc",
        "s4l",
        "s4lacad",
      ].includes(osparc.product.Utils.getProductName());
    },

    showQuality: function() {
      return this.isProduct("osparc");
    },

    showClassifiers: function() {
      return this.isProduct("osparc");
    },

    showConvertToPipeline: function() {
      return this.isS4LProduct() || this.isProduct("osparc");
    },

    showS4LStore: function() {
      const licensesEnabled = osparc.utils.DisabledPlugins.isLicensesEnabled();
      return this.isS4LProduct() && licensesEnabled;
    },

    showComputationalActivity: function() {
      if (this.isProduct("s4llite") || this.isProduct("tiplite")) {
        return false;
      }
      return true;
    },

    getDefaultWelcomeCredits: function() {
      switch (osparc.product.Utils.getProductName()) {
        case "s4l":
        case "s4lacad":
          return 100;
        default:
          return 0;
      }
    },

    getIconUrl: function(asset = "Default.png") {
      const base = "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/icons"
      let url;
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          url = `${base}/osparc/${asset}`;
          break;
        case "tis":
        case "tiplite":
          url = `${base}/tip/${asset}`;
          break;
        default:
          url = `${base}/s4l/${asset}`;
          break;
      }
      return url;
    },

    getThumbnailUrl: function(asset = "Default.png") {
      const base = "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails"
      let url;
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          url = `${base}/oSparc/${asset}`;
          break;
        case "tis":
        case "tiplite":
          url = `${base}/TIP/${asset}`;
          break;
        default:
          url = `${base}/S4L/${asset}`;
          break;
      }
      return url;
    },

    getBackgroundUrl: function(asset = "Thumbnail-01.png") {
      const base = "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images"
      let url;
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          url = `${base}/oSparc/${asset}`;
          break;
        case "tis":
        case "tiplite":
          url = `${base}/TIP/${asset}`;
          break;
        default:
          url = `${base}/S4L/${asset}`;
          break;
      }
      return url;
    },

    hasNewPlusButton: function() {
      return Boolean(osparc.store.Products.getInstance().getPlusButtonUiConfig());
    },

    groupServices: function() {
      return Boolean(osparc.store.Products.getInstance().getGroupedServicesUiConfig());
    },

    isSupportEnabled: function() {
      return Boolean(osparc.store.Products.getInstance().getSupportGroupId());
    },
  }
});
