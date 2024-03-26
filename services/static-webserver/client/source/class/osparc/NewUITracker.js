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
        const newReleaseAvailable = await osparc.NewRelease.checkNewRelease();
        if (newReleaseAvailable) {
          let msg = "";
          msg += this.tr("We are pleased to announce that some new features were deployed for you!");
          msg += "<br>";
          msg += this.tr("You might need to hard refresh the browser to get the latest version.");
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
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
