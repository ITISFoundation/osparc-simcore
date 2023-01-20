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
    // CHECK_INTERVAL: 30*60*1000, // Check every 30'
    CHECK_INTERVAL: 5*1000, // testing
    WARN_IN_ADVANCE: 20*60*1000 // Show Flash Message 20' in advance
  },

  members: {
    __checkInternval: null,
    __lastNotification: null,
    __lastFlashMessage: null,

    startTracker: function() {
      const checkMaintenance = () => {
        osparc.data.Resources.get("maintenance")
          .then(scheduledMaintenance => {
            if (scheduledMaintenance) {
              // for now it's just a string
              this.__setMaintenance(JSON.parse(scheduledMaintenance));
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

      let text = qx.locale.Manager.tr("Maintenance scheduled");
      if (this.getStart()) {
        text += "<br>";
        text += osparc.utils.Utils.formatDateAndTime(this.getStart());
      }
      if (this.getEnd()) {
        text += " - ";
        text += osparc.utils.Utils.formatDateAndTime(this.getEnd());
      }
      if (this.getReason()) {
        text += ": " + this.getReason();
      }
      text += "<br>";
      text += qx.locale.Manager.tr("Please, save your work and logout");
      return text;
    },

    __setMaintenance: function(maintenanceData) {
      const oldStart = this.getStart();
      const oldEnd = this.getEnd();
      const oldReason = this.getReason();
      if ("start" in maintenanceData) {
        const startDate = new Date(maintenanceData.start);
        this.setStart(startDate);
      }
      if ("end" in maintenanceData) {
        const endDate = new Date(maintenanceData.end);
        this.setEnd(new Date(endDate));
      }
      if ("reason" in maintenanceData) {
        const reason = maintenanceData.reason;
        this.setReason(reason);
      }

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
      this.__scheduleEnd();
    },

    __scheduleStart: function() {
      this.__addNotification();
      this.__scheduleFlashMessage();
      this.__scheduleLogout();
    },

    __addNotification: function() {
      if (this.__lastNotification) {
        osparc.component.notification.Notifications.getInstance().removeNotification(this.__lastNotification);
        this.__lastNotification = null;
      }
      const text = this.__getText();
      const notification = this.__lastNotification = new osparc.component.notification.NotificationUI(text);
      osparc.component.notification.Notifications.getInstance().addNotification(notification);
    },

    __scheduleFlashMessage: function() {
      if (this.__lastFlashMessage) {
        osparc.component.message.FlashMessenger.getInstance().removeMessage(this.__lastFlashMessage);
        this.__lastFlashMessage = null;
      }
      const popupMessage = () => {
        const now = new Date();
        const duration = this.getStart().getTime() - now.getTime();
        const text = this.__getText();
        this.__lastFlashMessage = osparc.component.message.FlashMessenger.getInstance().logAs(text, "WARNING", null, duration);
      };
      const now = new Date();
      const diff = this.getStart().getTime() - now.getTime() - this.self().WARN_IN_ADVANCE;
      if (diff < 0) {
        popupMessage();
      } else {
        setTimeout(() => popupMessage(), diff);
      }
    },

    __scheduleLogout: function() {
      const logoutUser = () => {
        qx.core.Init.getApplication().logout();
      };
      const now = new Date();
      const diff = this.getStart().getTime() - now.getTime();
      console.log("logout scheduled: ", this.getStart());
      setTimeout(() => logoutUser(), diff);
    },

    __scheduleEnd: function() {

    }
  }
});
