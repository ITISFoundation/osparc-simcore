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

  members: {
    __checkInternval: null,

    startTracker: function() {
      const checkMaintenance = () => {
        console.log("checkMaintenance");
        if (this.getStart()) {
          return;
        }
        // getMaintenance()
        if (Math.random() < 0.5) {
          const maintenanceData = {
            start: "2023-01-17T12:00:00.000Z",
            end: "2023-01-17T13:00:00.000Z",
            reason: "Release"
          };
          this.addMaintenance(maintenanceData);
        }
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

    addMaintenance: function(maintenanceData) {
      let text = qx.locale.Manager.tr("Maintenance scheduled");
      if ("start" in maintenanceData) {
        const startDate = new Date(maintenanceData.start);
        this.setStart(startDate);
        text += "<br>";
        text += osparc.utils.Utils.formatDateAndTime(startDate);
      }
      if ("end" in maintenanceData) {
        const endDate = new Date(maintenanceData.end);
        this.setEnd(new Date(endDate));
        text += " - ";
        text += osparc.utils.Utils.formatDateAndTime(endDate);
      }
      if ("reason" in maintenanceData) {
        const reason = maintenanceData.reason;
        this.setReason(reason);
        text += ": " + reason;
      }
      const notification = new osparc.component.notification.NotificationUI(text);
      osparc.component.notification.Notifications.getInstance().addNotification(notification);
    }
  }
});
