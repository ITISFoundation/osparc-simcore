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
    CLOSABLE_WARN_IN_ADVANCE: 4*24*60*60*1000, // Show Closable Ribbon Message 4 days in advance
    PERMANENT_WARN_IN_ADVANCE: 60*60*1000, // Show Permanent Ribbon Message 60' in advance

    dataToText: function(start, end, reason) {
      let text = osparc.utils.Utils.formatDateAndTime(start);
      if (end) {
        if (start.getDate() === end.getDate()) {
          // do not print the same day twice
          text += " - " + osparc.utils.Utils.formatTime(end);
        } else {
          text += " - " + osparc.utils.Utils.formatDateAndTime(end);
        }
      }
      text += " (local time)";
      if (reason) {
        text += ": " + reason;
      }
      return text;
    },
  },

  members: {
    __checkInterval: null,
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
      this.__checkInterval = setInterval(checkMaintenance, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInterval) {
        clearInterval(this.__checkInterval);
      }
    },

    __getText: function() {
      if (this.getStart() === null) {
        return null;
      }

      return this.self().dataToText(this.getStart(), this.getEnd(), this.getReason());
    },

    __setMaintenance: function(maintenanceData) {
      // ignore old maintenance
      if (maintenanceData && (new Date(maintenanceData.end).getTime() < new Date().getTime())) {
        console.warn(`Old maintenance "${maintenanceData.reason}" wasn't removed"`);
        return;
      }

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
        this.__scheduleStart();
      }
    },

    __scheduleStart: function() {
      this.__removeRibbonMessage();
      this.__removeScheduledLogout();

      if (this.getStart()) {
        this.__scheduleRibbonMessage();
        this.__scheduleLogout();
      }
    },

    messageToRibbon: function(closable, message = null) {
      this.__removeRibbonMessage();
      const text = message || this.__getText();
      const notification = new osparc.notification.RibbonNotification(text, "maintenance", closable);
      osparc.notification.RibbonNotifications.getInstance().addNotification(notification);
      this.__lastRibbonMessage = notification;
    },

    __scheduleRibbonMessage: function() {
      const now = new Date();
      const diffClosable = this.getStart().getTime() - now.getTime() - this.self().CLOSABLE_WARN_IN_ADVANCE;
      const diffPermanent = this.getStart().getTime() - now.getTime() - this.self().PERMANENT_WARN_IN_ADVANCE;

      if (diffClosable < 0) {
        this.messageToRibbon(true);
      } else {
        setTimeout(() => this.messageToRibbon(true), diffClosable);
      }
      if (diffPermanent < 0) {
        this.messageToRibbon(false);
      } else {
        setTimeout(() => this.messageToRibbon(false), diffPermanent);
      }
    },

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.notification.RibbonNotifications.getInstance().removeNotification(this.__lastRibbonMessage);
        this.__lastRibbonMessage = null;
      }
    },

    __logout: function() {
      this.set({
        start: null,
        end: null,
        reason: null
      });
      const reason = qx.locale.Manager.tr("The service is under maintenance. Please check back later");
      qx.core.Init.getApplication().logout(reason);
    },

    __scheduleLogout: function() {
      const now = new Date();
      if (this.getStart().getTime() > now.getTime()) {
        const diff = this.getStart().getTime() - now.getTime();
        this.__logoutTimer = setTimeout(() => this.__logout(), diff);
      } else if (this.getStart().getTime() < now.getTime() && this.getEnd().getTime() > now.getTime()) {
        this.__logout();
      }
    },

    __removeScheduledLogout: function() {
      if (this.__logoutTimer) {
        clearTimeout(this.__logoutTimer);
      }
    }
  }
});
