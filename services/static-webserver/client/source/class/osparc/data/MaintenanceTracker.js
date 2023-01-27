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

qx.Class.define("osparc.data.MaintenanceTracker", {
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
    CHECK_INTERVAL: 15*1000, // Check every 15'
    WARN_IN_ADVANCE: 20*60*1000 // Show Ribbon Message 20' in advance
  },

  members: {
    __checkInternval: null,
    __lastNotification: null,
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

    __getText: function(wDecoration = true) {
      if (this.getStart() === null) {
        return null;
      }

      let text = wDecoration ? qx.locale.Manager.tr("Maintenance scheduled.") : "";
      if (this.getStart()) {
        text += wDecoration ? "<br>" : "";
        text += osparc.utils.Utils.formatDateAndTime(this.getStart());
      }
      if (this.getEnd()) {
        text += " - " + osparc.utils.Utils.formatDateAndTime(this.getEnd());
      }
      if (this.getReason()) {
        text += ": " + this.getReason();
      }
      text += wDecoration ? "<br>" + qx.locale.Manager.tr("Please save your work and logout.") : "";
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
        this.__removeNotification();
        this.__removeRibbonMessage();
        this.__removeScheduledLogout();
      } else {
        this.__addNotification();
        this.__scheduleRibbonMessage();
        this.__scheduleLogout();
      }
    },

    __addNotification: function() {
      this.__removeNotification();

      const text = this.__getText();
      const notification = this.__lastNotification = new osparc.component.notification.NotificationUI(text);
      osparc.component.notification.Notifications.getInstance().addNotification(notification);
    },

    __removeNotification: function() {
      if (this.__lastNotification) {
        osparc.component.notification.Notifications.getInstance().removeNotification(this.__lastNotification);
        this.__lastNotification = null;
      }
    },

    __scheduleRibbonMessage: function() {
      this.__removeRibbonMessage();

      const messageToRibbon = () => {
        const text = this.__getText(false);
        const notification = new osparc.component.notification.Notification(text);
        this.__lastRibbonMessage = osparc.component.notification.NotificationsRibbon.getInstance().addNotification(notification);
      };
      const now = new Date();
      const diff = this.getStart().getTime() - now.getTime() - this.self().WARN_IN_ADVANCE;
      if (diff < 0) {
        messageToRibbon();
      } else {
        setTimeout(() => messageToRibbon(), diff);
      }
    },

    __removeRibbonMessage: function() {
      if (this.__lastRibbonMessage) {
        osparc.component.message.FlashMessenger.getInstance().removeMessage(this.__lastRibbonMessage);
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
        osparc.component.message.FlashMessenger.getInstance().logAs(text, "WARNING");
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
