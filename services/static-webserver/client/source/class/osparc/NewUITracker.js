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
    // CHECK_INTERVAL: 60*60*1000 // Check every 60'
    CHECK_INTERVAL: 10*1000
  },

  members: {
    __checkInterval: null,

    startTracker: function() {
      const checkNewUI = async () => {
        const newReleaseAvailable = await osparc.NewRelease.isMyFrontendOld();
        if (newReleaseAvailable) {
          let msg = "";
          msg += osparc.NewRelease.getText();
          msg += "<br>";
          msg += qx.locale.Manager.tr("You might need to hard refresh the browser to get the latest version.");
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
