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
      const latestS4LVersion = osparc.store.Services.getLatest(osparc.NewReleaseS4L.S4L_SERVICE_KEY);
      if (lastS4LVersion && latestS4LVersion) {
        isNewRelease = lastS4LVersion !== latestS4LVersion;
      }
      osparc.utils.Utils.localCache.setLatestSim4LifeVersion(latestS4LVersion);
      return isNewRelease;
    },
  },
});
