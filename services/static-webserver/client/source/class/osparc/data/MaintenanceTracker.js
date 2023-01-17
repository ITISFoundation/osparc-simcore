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
        if (this.getStart()) {
          return;
        }
        // getMaintenance()
        console.log("getMaintenance");
      };
      checkMaintenance();
      const interval = 60*1000;
      this.__checkInternval = setInterval(checkMaintenance, interval);
    },

    stopTracker: function() {
      if (this.__checkInternval) {
        clearInterval(this.__checkInternval);
      }
    },

    addMaintenance: function(maintenanceData) {
      console.log("addMaintenance", maintenanceData);
    }
  }
});
