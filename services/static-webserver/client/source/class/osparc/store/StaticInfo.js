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

  members: {
    getValue: function(key) {
      const statics = osparc.store.Store.getInstance().get("statics");
      if (key in statics) {
        return statics[key];
      }
      const errorMsg = `${key} not found in statics`;
      console.warn(errorMsg);
      return null;
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
