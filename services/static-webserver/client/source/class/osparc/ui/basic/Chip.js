/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.basic.Chip", {
  extend: qx.ui.basic.Atom,

  construct: function(label, icon) {
    this.base(arguments, label, icon);

    this.set({
      allowGrowX: false,
    });
  },

  properties: {
    appearance: {
      init: "chip",
      refine: true
    },

    statusColor: {
      check: ["success", "warning", "error"],
      init: null,
      apply: "__applyStatusColor",
    },
  },

  statics: {
    STATUS: {
      SUCCESS: "success",
      WARNING: "warning",
      ERROR: "error",
    },
  },

  members: {
    __applyStatusColor: function(status) {
      switch (status.toLowerCase()) {
        case this.self().STATUS.SUCCESS:
          this.set({
            textColor: "white",
            backgroundColor: "product-color",
          });
          break;
        case this.self().STATUS.WARNING:
          this.set({
            textColor: "black",
            backgroundColor: "warning-yellow",
          });
          break;
        case this.self().STATUS.ERROR:
          this.set({
            textColor: "black",
            backgroundColor: "failed-red",
          });
          break;
      }
    },
  },
});
