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
      if (this.getProductName().includes("s4l")) {
        if (options.plural) {
          alias = qx.locale.Manager.tr("projects");
        } else {
          alias = qx.locale.Manager.tr("project");
        }
      } else if (options.plural) {
        alias = qx.locale.Manager.tr("studies");
      } else {
        alias = qx.locale.Manager.tr("study");
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
      if (this.getProductName().includes("s4l")) {
        if (options.plural) {
          alias = qx.locale.Manager.tr("tutorials");
        } else {
          alias = qx.locale.Manager.tr("tutorial");
        }
      } else if (options.plural) {
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

    resourceTypeToAlias: function(resourceType, options) {
      switch (resourceType) {
        case "study":
          return this.getStudyAlias(options);
        case "template":
          return this.getTemplateAlias(options);
        case "service":
          return this.getServiceAlias(options);
      }
      return resourceType;
    },

    __linkExists: function(url) {
      return new Promise((resolve, reject) => {
        const reqSvg = new XMLHttpRequest();
        reqSvg.open("GET", url, true);
        reqSvg.onreadystatechange = () => {
          if (reqSvg.readyState === 4) {
            if (reqSvg.status === 404) {
              reject();
            } else {
              resolve();
            }
          }
        };
        reqSvg.send();
      });
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
      return (this.isS4LProduct() || this.isProduct("s4llite"));
    },

    showPreferencesTokens: function() {
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

    showClusters: function() {
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

    showQuality: function() {
      if (this.isProduct("osparc")) {
        return true;
      }
      return false;
    },

    showClassifiers: function() {
      if (this.getProductName().includes("s4l")) {
        return false;
      }
      return true;
    },

    showS4LStore: function() {
      const platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
      if (platformName !== "master") {
        return false;
      }
      return this.isS4LProduct();
    },

    getProductThumbUrl: function(asset = "Default.png") {
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

    getProductBackgroundUrl: function(asset = "Thumbnail-01.png") {
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
    }
  }
});
