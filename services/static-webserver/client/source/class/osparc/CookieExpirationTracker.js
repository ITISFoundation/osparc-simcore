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

  properties: {
    start: {
      check: "Date",
      init: null,
      nullable: true
    },

    end: {
      check: "Date",
      init: null,
      nullable: true
    },

    reason: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  statics: {
    CHECK_INTERVAL: 15*60*1000, // Check every 15'
    PERMANENT_WARN_IN_ADVANCE: 60*60*1000 // Show Ribbon Permanent Message 1h in advance
  },

  members: {
    __checkInterval: null,
    __logoutTimer: null,

    startTracker: function() {
      const checkCookieExpiration = () => {
        this.__scheduleStart();
      };
      checkCookieExpiration();
      this.__checkInterval = setInterval(checkCookieExpiration, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInterval) {
        clearInterval(this.__checkInterval);
      }
    },

    __getText: function() {
      const text = this.tr("You session will expire in 1h. Please, log out and log in again.");
      return text;
    },

    __scheduleStart: function() {
      this.__showRibbonMessage();
      this.__scheduleLogout();
    },

    __showRibbonMessage: function() {
      const now = new Date();
      const diffClosable = this.getStart().getTime() - now.getTime() - this.self().CLOSABLE_WARN_IN_ADVANCE;
      const diffPermanent = this.getStart().getTime() - now.getTime() - this.self().PERMANENT_WARN_IN_ADVANCE;

      const messageToRibbon = () => {
        const text = this.__getText();
        const closable = false;
        const notification = new osparc.notification.RibbonNotification(text, "maintenance", closable);
        osparc.notification.RibbonNotifications.getInstance().addNotification(notification);
      };
      if (diffClosable < 0) {
        messageToRibbon(true);
      } else {
        setTimeout(() => messageToRibbon(true), diffClosable);
      }
      if (diffPermanent < 0) {
        messageToRibbon(false);
      } else {
        setTimeout(() => messageToRibbon(false), diffPermanent);
      }
    },

    __scheduleLogout: function() {
      this.__removeScheduledLogout();

      const logoutUser = () => {
        this.set({
          start: null,
          end: null,
          reason: null
        });
        let text = qx.locale.Manager.tr("We are under maintenance.");
        text += "<br>";
        text += qx.locale.Manager.tr("Please check back later");
        osparc.FlashMessenger.getInstance().logAs(text, "WARNING");
        qx.core.Init.getApplication().logout();
      };
      const now = new Date();
      if (this.getStart().getTime() > now.getTime()) {
        const diff = this.getStart().getTime() - now.getTime();
        this.__logoutTimer = setTimeout(() => logoutUser(), diff);
      } else if (this.getStart().getTime() < now.getTime() && this.getEnd().getTime() > now.getTime()) {
        logoutUser();
      }
    },

    __removeScheduledLogout: function() {
      if (this.__logoutTimer) {
        clearTimeout(this.__logoutTimer);
      }
    }
  }
});
