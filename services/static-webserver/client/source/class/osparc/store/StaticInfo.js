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
      const staticKey = "stackName";
      const stackName = this.getValue(staticKey);
      let platformName = "dev";
      if (stackName.includes("master")) {
        platformName = "master";
      } else if (stackName.includes("staging")) {
        platformName = "staging";
      } else if (stackName.includes("production")) {
        platformName = "";
      }
      return platformName;
    },

    getDisplayName: function() {
      const staticKey = "displayName";
      return this.getValue(staticKey);
    },

    getReleaseData: function() {
      const rTag = this.getValue("vcsReleaseTag");
      const rDate = this.getValue("vcsReleaseDate");
      const rUrl = this.getValue("vcsReleaseUrl");
      return {
        "tag": rTag,
        "date": rDate,
        "url": rUrl
      };
    },

    getMaxNumberDyNodes: function() {
      const staticKey = "webserverProjects";
      const wsStaticData = this.getValue(staticKey)
      const key = "PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES";
      if (key in wsStaticData) {
        return wsStaticData[key];
      }
      return null;
    }
  }
});
