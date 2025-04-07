/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for studies
 */

qx.Class.define("osparc.utils.DisabledPlugins", {
  type: "static",

  statics: {
    EXPORT: "WEBSERVER_EXPORTER",
    IMPORT: "WEBSERVER_EXPORTER",
    SCICRUNCH: "WEBSERVER_SCICRUNCH",
    VERSION_CONTROL: "WEBSERVER_VERSION_CONTROL",
    META_MODELING: "WEBSERVER_META_MODELING",
    LICENSES: "WEBSERVER_LICENSES",
    SHARE_WITH_EMAIL: "WEBSERVER_SHARE_WITH_EMAIL",

    isExportDisabled: function() {
      return this.__isPluginDisabled(this.EXPORT);
    },

    isImportDisabled: function() {
      // Import is disabled until an Export (full not cMIS only) function is implemented
      return true;
      // return this.__isPluginDisabled(this.EXPORT);
    },

    isVersionControlDisabled: function() {
      return this.__isPluginDisabled(this.VERSION_CONTROL);
    },

    isMetaModelingDisabled: function() {
      return this.__isPluginDisabled(this.META_MODELING);
    },

    isLicensesDisabled: function() {
      return this.__isPluginDisabled(this.LICENSES);
    },

    isShareWithEmailEnabled: function() {
      // return !this.__isPluginDisabled(this.SHARE_WITH_EMAIL);
      return new Promise(resolve => resolve(true));
    },

    isJobsEnabled: function() {
      if (osparc.utils.Utils.isDevelopmentPlatform() && osparc.product.Utils.isProduct("s4lacad")) {
        return true;
      }
      return false;
    },

    __isPluginDisabled: function(key) {
      const statics = osparc.store.Store.getInstance().get("statics");
      if (statics) {
        if ("pluginsDisabled" in statics) {
          return statics["pluginsDisabled"].includes(key);
        }
      }
      return false;
    }
  }
});
