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
      if ("start" in maintenanceData) {
        this.setStart(new Date(maintenanceData.start));
      }
      if ("end" in maintenanceData) {
        this.setEnd(new Date(maintenanceData.end));
      }
      if ("reason" in maintenanceData) {
        this.setReason(maintenanceData.reason);
      }
    }
  }
});
