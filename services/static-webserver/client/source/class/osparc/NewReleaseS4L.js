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
  type: "static",

  statics: {
    S4L_SERVICE_KEY: "simcore/services/dynamic/s4l-ui",

    /**
     * Compare the sim4life version in the browser cache with the latest one received.
     * Returns true if there is at least a minor version change, ignoring patch and pre-release.
     * @returns {boolean}
     */
    isNewRelease: function() {
      const lastS4LVersion = osparc.utils.Utils.localCache.getLatestSim4LifeVersion();
      const latestS4L = osparc.store.Services.getLatest(osparc.NewReleaseS4L.S4L_SERVICE_KEY);
      const latestS4LVersion = latestS4L && latestS4L["versionDisplay"] ? latestS4L["versionDisplay"] : null;

      let isNewRelease = false;
      if (lastS4LVersion && latestS4LVersion) {
        isNewRelease = osparc.utils.Utils.hasMinorOrMajorBump(lastS4LVersion, latestS4LVersion);
      }

      if (latestS4LVersion) {
        osparc.utils.Utils.localCache.setLatestSim4LifeVersion(latestS4LVersion);
      }
      return isNewRelease;
    },
  },
});
