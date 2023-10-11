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
    CLUSTERS: "WEBSERVER_CLUSTERS",

    isExportDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isImportDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isVersionControlDisabled: function() {
      return this.self().isPluginDisabled(this.self().VERSION_CONTROL);
    },

    isMetaModelingDisabled: function() {
      return this.self().isPluginDisabled(this.self().META_MODELING);
    },

    isClustersDisabled: function() {
      return this.self().isPluginDisabled(this.self().CLUSTERS);
    },

    isPluginDisabled: function(key) {
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
