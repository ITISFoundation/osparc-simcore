/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.NewUITracker", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    CHECK_INTERVAL: 60*60*1000 // Check every 60'
  },

  members: {
    __checkInterval: null,

    startTracker: function() {
      const checkNewUI = async () => {
        const newReleaseAvailable = await osparc.NewRelease.isMyFrontendOld();
        if (newReleaseAvailable) {
          let msg = "";
          msg += qx.locale.Manager.tr("A new version of the application is now available.");
          msg += "<br>";
          msg += qx.locale.Manager.tr("Reload to get the latest features.");
          // permanent message
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO", 0);
          this.stopTracker();
        }
      };
      checkNewUI();
      this.__checkInterval = setInterval(checkNewUI, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInterval) {
        clearInterval(this.__checkInterval);
      }
    }
  }
});
