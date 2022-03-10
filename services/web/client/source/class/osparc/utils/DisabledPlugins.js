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
    DUPLICATE: "WEBSERVER_EXPORTER",
    IMPORT: "WEBSERVER_EXPORTER",
    SCICRUNCH: "WEBSERVER_SCICRUNCH",
    VERSION_CONTROL: "WEBSERVER_VERSION_CONTROL",
    META_MODELING: "WEBSERVER_META_MODELING",

    isExportDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isDuplicateDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isImportDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isScicrunchDisabled: function() {
      return this.self().isPluginDisabled(this.self().SCICRUNCH);
    },

    isVersionControlDisabled: function() {
      return this.self().isPluginDisabled(this.self().VERSION_CONTROL);
    },

    isMetaModelingDisabled: function() {
      return this.self().isPluginDisabled(this.self().META_MODELING);
    },

    isPluginDisabled: function(key) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.get("statics")
          .then(statics => {
            if ("pluginsDisabled" in statics) {
              resolve(statics["pluginsDisabled"].includes(key));
            }
            resolve(false);
          })
          .catch(err => reject(err));
      });
    }
  }
});
