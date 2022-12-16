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

qx.Class.define("osparc.store.StaticInfo", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    osparc.data.Resources.get("statics");
  },

  members: {
    getValue: function(key) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.get("statics")
          .then(staticData => {
            if (key in staticData) {
              resolve(staticData[key]);
            } else {
              const errorMsg = `${key} not found in statics`;
              console.warn(errorMsg);
              reject(errorMsg);
            }
          })
          .catch(err => reject(err));
      });
    },

    getDisplayName: function() {
      const wsKey = "displayName";
      return this.getValue(wsKey);
    },

    getMaxNumberDyNodes: function() {
      return new Promise(resolve => {
        const wsKey = "webserverProjects";
        this.getValue(wsKey)
          .then(wsStaticData => {
            const key = "PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES";
            if (key in wsStaticData) {
              resolve(wsStaticData[key]);
            } else {
              resolve(null);
            }
          })
          .catch(() => resolve(null));
      });
    }
  }
});
