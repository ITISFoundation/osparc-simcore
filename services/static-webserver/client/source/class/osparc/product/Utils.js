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

    getStudyAlias: function(options = {}) {
      let alias = null;
      const product = this.getProductName();
      switch (product) {
        case "s4l":
        case "s4llite":
        case "s4lacad":
          if (options.plural) {
            alias = qx.locale.Manager.tr("projects");
          } else {
            alias = qx.locale.Manager.tr("project");
          }
          break;
        default:
          if (options.plural) {
            alias = qx.locale.Manager.tr("studies");
          } else {
            alias = qx.locale.Manager.tr("study");
          }
          break;
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
      const product = this.getProductName();
      switch (product) {
        case "s4l":
        case "s4llite":
        case "s4lacad":
          if (options.plural) {
            alias = qx.locale.Manager.tr("tutorials");
          } else {
            alias = qx.locale.Manager.tr("tutorial");
          }
          break;
        default:
          if (options.plural) {
            alias = qx.locale.Manager.tr("templates");
          } else {
            alias = qx.locale.Manager.tr("template");
          }
          break;
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
              logosPath = "osparc/s4l_logo_white.svg";
            } else {
              logosPath = "osparc/s4l_logo_white_short.svg";
            }
          } else if (longLogo) {
            logosPath = "osparc/s4l_logo_black.svg";
          } else {
            logosPath = "osparc/s4l_logo_black_short.svg";
          }
          break;
        }
        case "s4llite":
          logosPath = lightLogo ? "osparc/s4llite-white.png" : "osparc/s4llite-black.png";
          break;
        case "s4lacad":
          logosPath = lightLogo ? "osparc/s4lacad-white.png" : "osparc/s4lacad-black.png";
          break;
        case "tis":
          logosPath = lightLogo ? "osparc/tip_itis-white.svg" : "osparc/tip_itis-black.svg";
          break;
        default:
          logosPath = lightLogo ? "osparc/osparc-white.svg" : "osparc/osparc-black.svg";
          break;
      }
      return logosPath;
    },

    getWorkbenchUIPreviewPath: function() {
      const colorManager = qx.theme.manager.Color.getInstance();
      const textColor = colorManager.resolve("text");
      const darkImage = osparc.utils.Utils.getColorLuminance(textColor) > 0.4;
      return darkImage ? "osparc/workbenchUI-dark.png" : "osparc/workbenchUI-light.png";
    },

    showLicenseExtra: function() {
      if (this.isProduct("osparc")) {
        return false;
      }
      return true;
    },

    showStudyPreview: function(studyData) {
      const uiMode = osparc.data.model.Study.getUiMode(studyData);
      if (uiMode && uiMode === "app") {
        return false;
      }
      return true;
    },

    showAboutProduct: function() {
      if (this.isProduct("osparc")) {
        return false;
      }
      return true;
    },

    showPreferencesTokens: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis")) {
        return false;
      }
      return true;
    },

    showPreferencesExperimental: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis")) {
        return false;
      }
      return true;
    },

    showClusters: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis")) {
        return false;
      }
      return true;
    },

    showDisableServiceAutoStart: function() {
      if (this.isProduct("s4llite") || this.isProduct("tis")) {
        return false;
      }
      return true;
    },

    showQuality: function() {
      if (this.isProduct("s4l") || this.isProduct("s4llite") || this.isProduct("s4lacad")) {
        return false;
      }
      return true;
    },

    showClassifiers: function() {
      if (this.isProduct("s4l") || this.isProduct("s4llite") || this.isProduct("s4lacad")) {
        return false;
      }
      return true;
    }
  }
});
