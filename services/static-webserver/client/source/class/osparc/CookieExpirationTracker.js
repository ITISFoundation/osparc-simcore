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
    PERMANENT_WARN_IN_ADVANCE: 2*60*60*1000, // Show Permanent Flash Message 2h in advance
    LOG_OUT_BEFORE_EXPIRING: 60*1000 // Log user out 1' in before expiring
  },

  properties: {
    expirationDate: {
      check: "Date",
      nullable: false,
      init: null,
      apply: "__startInterval"
    }
  },

  members: {
    __updateInterval: null,
    __message: null,
    __messageInterval: null,

    startTracker: function() {
      const cookieMaxAge = osparc.store.StaticInfo.getInstance().getCookieMaxAge(); // seconds
      if (cookieMaxAge) {
        const nowDate = new Date();
        const expirationDateMilliseconds = nowDate.getTime() + cookieMaxAge*1000;
        this.setExpirationDate(new Date(expirationDateMilliseconds));
      }
    },

    stopTracker: function() {
      if (this.__updateInterval) {
        clearInterval(this.__updateInterval);
      }

      this.__removeFlashMessage();
    },

    __startInterval: function() {
      this.__checkTimes();
      // check every 1' if the countdown routine needs to be started
      this.__updateInterval = setInterval(() => this.__checkTimes(), 60*1000);
    },

    __checkTimes: function() {
      const nowDate = new Date();
      const expirationDate = this.getExpirationDate();
      if (nowDate.getTime() + this.self().PERMANENT_WARN_IN_ADVANCE > expirationDate.getTime()) {
        this.__removeFlashMessage();
        this.__displayFlashMessage(parseInt((expirationDate.getTime() - nowDate.getTime())/1000));
      }
      if (nowDate.getTime() + this.self().LOG_OUT_BEFORE_EXPIRING > expirationDate.getTime()) {
        this.__logoutUser();
      }
    },

    // FLASH MESSAGE //
    __displayFlashMessage: function(willExpireIn) {
      const updateFlashMessage = () => {
        if (willExpireIn <= 0) {
          this.__removeFlashMessage();
          return;
        }

        this.__updateFlashMessage(willExpireIn);
        willExpireIn--;
      };
      updateFlashMessage();
      this.__messageInterval = setInterval(updateFlashMessage, 1000); // update every second
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

    __updateFlashMessage: function(timeoutSec) {
      const timeout = osparc.utils.Utils.formatSeconds(timeoutSec);
      const text = qx.locale.Manager.tr(`Your session will expire in ${timeout}.<br>Please log out and log in again.`);
      if (this.__message === null) {
        this.__message = osparc.FlashMessenger.logAs(text, "WARNING", timeoutSec*1000);
        this.__message.getChildControl("closebutton").exclude();
      } else {
        this.__message.setMessage(text);
      }
    },
    // /FLASH MESSAGE //

    __logoutUser: function() {
      const reason = qx.locale.Manager.tr("Your session has expired");
      qx.core.Init.getApplication().logout(reason);
    }
  }
});
