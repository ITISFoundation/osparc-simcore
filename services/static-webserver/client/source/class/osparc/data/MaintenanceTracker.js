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
    WARN_IN_ADVANCE: 20*60*1000 // Show Flash Message 20' in advance
  },

  members: {
    __checkInternval: null,

    startTracker: function() {
      const checkMaintenance = () => {
        if (this.getStart()) {
          return;
        }
        osparc.data.Resources.get("maintenance")
          .then(scheduledMaintenance => {
            if (scheduledMaintenance) {
              this.__setMaintenance(scheduledMaintenance);
            }
          })
          .catch(err => console.error(err));
      };
      checkMaintenance();
      const interval = 2*1000;
      this.__checkInternval = setInterval(checkMaintenance, interval);
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

      const text = this.__getText();
      const notification = new osparc.component.notification.NotificationUI(text);
      osparc.component.notification.Notifications.getInstance().addNotification(notification);

      this.__scheduleMaintenance();

      this.stopTracker();
    },

    __scheduleMaintenance: function() {
      this.__scheduleFlashMessage();
      this.__scheduleLogout();
    },

    __scheduleFlashMessage: function() {
      const popupMessage = () => {
        const now = new Date();
        const duration = this.getStart().getTime() - now.getTime();
        const text = this.__getText();
        osparc.component.message.FlashMessenger.getInstance().logAs(text, "WARNING", null, duration);
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
    }
  }
});
