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

    getPlatformName: function() {
      return new Promise(resolve => {
        const staticKey = "stackName";
        this.getValue(staticKey)
          .then(stackName => {
            let platformName = "dev";
            if (stackName.includes("master")) {
              platformName = "master";
            } else if (stackName.includes("staging")) {
              platformName = "staging";
            } else if (stackName.includes("production")) {
              platformName = "";
            }
            resolve(platformName);
          });
      });
    },

    getDisplayName: function() {
      const staticKey = "displayName";
      return this.getValue(staticKey);
    },

    getReleaseData: function() {
      return new Promise(resolve => {
        Promise.all([
          this.getValue("vcsReleaseTag"),
          this.getValue("vcsReleaseDate"),
          this.getValue("vcsReleaseUrl")
        ]).then(values => {
          const rTag = values[0];
          const rDate = values[1];
          const rUrl = values[2];
          resolve({
            "tag": rTag,
            "date": rDate,
            "url": rUrl
          });
        }).catch(() => resolve(null));
      });
    },

    getMaxNumberDyNodes: function() {
      return new Promise(resolve => {
        const staticKey = "webserverProjects";
        this.getValue(staticKey)
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
