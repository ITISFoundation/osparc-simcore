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

qx.Class.define("osparc.CookieExpirationTracker", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    PERMANENT_WARN_IN_ADVANCE: 60*60, // Show Permanent Flash Message 1h in advance
    LOG_OUT_BEFORE_EXPIRING: 60 // Log user out 1' in before expiring
  },

  members: {
    __message: null,
    __messageTimer: null,
    __messageInterval: null,
    __logoutTimer: null,

    startTracker: function() {
      const cookieMaxAge = osparc.store.StaticInfo.getInstance().getCookieMaxAge();
      if (cookieMaxAge) {
        const nowDate = new Date();
        const expirationTime = nowDate.getTime() + cookieMaxAge*1000 - this.self().LOG_OUT_BEFORE_EXPIRING*1000;
        const expirationDate = new Date(expirationTime);
        const showMessageIn = Math.max(cookieMaxAge - this.self().PERMANENT_WARN_IN_ADVANCE, 0);
        this.__messageTimer = setTimeout(() => {
          const willExpireIn = parseInt((expirationDate - nowDate)/1000);
          this.__displayFlashMessage(willExpireIn);
        }, showMessageIn*1000);

        const logOutIn = Math.max(cookieMaxAge - this.self().LOG_OUT_BEFORE_EXPIRING, 0);
        this.__logoutTimer = setTimeout(() => this.__logoutUser(), logOutIn*1000);
      }
    },

    stopTracker: function() {
      if (this.__messageTimer) {
        clearTimeout(this.__messageTimer);
      }
      if (this.__logoutTimer) {
        clearTimeout(this.__logoutTimer);
      }

      this.__removeFlashMessage();
    },

    __displayFlashMessage: function(willExpireIn) {
      const updateFlashMessage = () => {
        if (willExpireIn <= 0) {
          this.__removeFlashMessage();
          return;
        }

        this.__updateFlashMessage(willExpireIn);
        willExpireIn--;
      };
      this.__messageInterval = setInterval(updateFlashMessage, 1000);
    },

    __removeFlashMessage: function() {
      // removes a flash message if displaying
      if (this.__messageInterval) {
        clearInterval(this.__messageInterval);
      }
      if (this.__message) {
        osparc.FlashMessenger.getInstance().removeMessage(this.__message);
        this.__message = null;
      }
    },

    __updateFlashMessage: function(timeoutSec = 1000) {
      const timeout = osparc.utils.Utils.formatSeconds(timeoutSec);
      const text = qx.locale.Manager.tr(`Your session will expire in ${timeout}.<br>Please log out and log in again.`);
      if (this.__message === null) {
        this.__message = osparc.FlashMessenger.getInstance().logAs(text, "WARNING", timeoutSec*1000);
      } else {
        this.__message.setMessage(text);
      }
    },

    __logoutUser: function() {
      const reason = qx.locale.Manager.tr("Session expired");
      qx.core.Init.getApplication().logout(reason);
    }
  }
});
