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
    SCICRUNCH: "WEBSERVER_SCICRUNCH",
    CHECKPOINTS: "WEBSERVER_CHECKPOINTS",

    isExportDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isDuplicateDisabled: function() {
      return this.self().isPluginDisabled(this.self().EXPORT);
    },

    isScicrunchDisabled: function() {
      return this.self().isPluginDisabled(this.self().SCICRUNCH);
    },

    isCheckpointsDisabled: function() {
      return this.self().isPluginDisabled(this.self().CHECKPOINTS);
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
