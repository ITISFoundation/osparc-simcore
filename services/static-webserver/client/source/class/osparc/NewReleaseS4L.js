/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.NewReleaseS4L", {
  extend: qx.ui.core.Widget,

  statics: {
    S4L_SERVICE_KEY: "simcore/services/dynamic/s4l-ui",

    /**
     * Compare the sim4life version in the browser cache with the latest one received
     */
    isNewRelease: function() {
      let isNewRelease = false;
      const lastS4LVersion = osparc.utils.Utils.localCache.getLatestSim4LifeVersion();
      const latestS4L = osparc.store.Services.getLatest(osparc.NewReleaseS4L.S4L_SERVICE_KEY);
      const latestS4LVersion = latestS4L && latestS4L["versionDisplay"] ? latestS4L["versionDisplay"] : null;
      if (lastS4LVersion && latestS4LVersion) {
        // set it to true if there is a at least a minor version change, ignoring patch changes
        const [lastMajor, lastMinor] = lastS4LVersion.split(".").map(Number);
        const [latestMajor, latestMinor] = latestS4LVersion.split(".").map(Number);
        isNewRelease = lastMajor !== latestMajor || lastMinor !== latestMinor;
      }
      osparc.utils.Utils.localCache.setLatestSim4LifeVersion(latestS4LVersion);
      return isNewRelease;
    },
  },
});
