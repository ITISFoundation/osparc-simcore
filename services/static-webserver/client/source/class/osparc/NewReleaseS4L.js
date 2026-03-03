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
     * Parses a version string (e.g. "9.4.0" or "9.4.0-rc.5") into its components.
     * @param {string} version - Version string in semver format
     * @returns {{ major: number, minor: number, patch: number, preRelease: string|null }}
     */
    parseVersion: function(version) {
      const [semver, ...preReleaseParts] = version.split("-");
      const [major, minor, patch] = semver.split(".").map(Number);
      return {
        major,
        minor,
        patch: patch || 0,
        preRelease: preReleaseParts.length ? preReleaseParts.join("-") : null,
      };
    },

    /**
     * Returns true if major or minor version differs between two version strings.
     * @param {string} versionA
     * @param {string} versionB
     * @returns {boolean}
     */
    hasMinorOrMajorBump: function(versionA, versionB) {
      const a = osparc.NewReleaseS4L.parseVersion(versionA);
      const b = osparc.NewReleaseS4L.parseVersion(versionB);
      return a.major !== b.major || a.minor !== b.minor;
    },

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
        isNewRelease = osparc.NewReleaseS4L.hasMinorOrMajorBump(lastS4LVersion, latestS4LVersion);
      }

      osparc.utils.Utils.localCache.setLatestSim4LifeVersion(latestS4LVersion);
      return isNewRelease;
    },
  },
});
