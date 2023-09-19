/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.MaintenanceTracker", {
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
    CLOSABLE_WARN_IN_ADVANCE: 24*60*60*1000, // Show Ribbon Closable Message 24h in advance
    PERMANENT_WARN_IN_ADVANCE: 30*60*1000 // Show Ribbon Permament Message 30' in advance
  },

  members: {
    __checkInternval: null,
    __lastRibbonMessage: null,
    __logoutTimer: null,

    startTracker: function() {
      const checkMaintenance = () => {
        osparc.data.Resources.get("maintenance")
          .then(scheduledMaintenance => {
            if (scheduledMaintenance) {
              // for now it's just a string
              this.__setMaintenance(JSON.parse(scheduledMaintenance));
            } else {
              this.__setMaintenance(null);
            }
          })
          .catch(err => console.error(err));
      };
      checkMaintenance();
      this.__checkInternval = setInterval(checkMaintenance, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInternval) {
        clearInterval(this.__checkInternval);
      }
    },

    __getText: function() {
      if (this.getStart() === null) {
        return null;
      }

      let text = osparc.utils.Utils.formatDateAndTime(this.getStart());
      if (this.getEnd()) {
        if (this.getStart().getDate() === this.getEnd().getDate()) {
          // do not print the same day twice
          text += " - " + osparc.utils.Utils.formatTime(this.getEnd());
        } else {
          text += " - " + osparc.utils.Utils.formatDateAndTime(this.getEnd());
        }
      }
      text += " (local time)";
      if (this.getReason()) {
        text += ": " + this.getReason();
      }
      return text;
    },

    __setMaintenance: function(maintenanceData) {
      const oldStart = this.getStart();
      const oldEnd = this.getEnd();
      const oldReason = this.getReason();

      this.setStart(maintenanceData && "start" in maintenanceData ? new Date(maintenanceData.start) : null);
      this.setEnd(maintenanceData && "end" in maintenanceData ? new Date(maintenanceData.end) : null);
      this.setReason(maintenanceData && "reason" in maintenanceData ? maintenanceData.reason : null);

      if (
        maintenanceData === null || // it will remove it
        (oldStart === null || oldStart.getTime() !== this.getStart().getTime()) ||
        (oldEnd === null || oldEnd.getTime() !== this.getEnd().getTime()) ||
        oldReason !== this.getReason()
      ) {
        this.__scheduleMaintenance();
      }
    },

    __scheduleMaintenance: function() {
      this.__scheduleStart();
    },

    __scheduleStart: function() {
      if (this.getStart() === null) {
        this.__removeRibbonMessage();
        this.__removeScheduledLogout();
      } else {
        this.__scheduleRibbonMessage();
        this.__scheduleLogout();
      }
    },

    __scheduleRibbonMessage: function() {
      this.__removeRibbonMessage();

      const now = new Date();
      const diffClosable = this.getStart().getTime() - now.getTime() - this.self().CLOSABLE_WARN_IN_ADVANCE;
      const diffPermanent = this.getStart().getTime() - now.getTime() - this.self().PERMANENT_WARN_IN_ADVANCE;

      const messageToRibbon = closable => {
        this.__removeRibbonMessage();
        const text = this.__getText();
        const notification = new osparc.notification.RibbonNotification(text, "maintenance", closable);
        osparc.notification.RibbonNotifications.getInstance().addNotification(notification);
        this.__lastRibbonMessage = notification;
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

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.notification.RibbonNotifications.getInstance().removeNotification(this.__lastRibbonMessage);
        this.__lastRibbonMessage = null;
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
