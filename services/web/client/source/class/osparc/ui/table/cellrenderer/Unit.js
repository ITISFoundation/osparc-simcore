/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.table.cellrenderer.Unit", {
  extend: qx.ui.table.cellrenderer.Html,

  construct: function(unit) {
    this.base(arguments, "center");
    this.setUnit(unit);
  },

  properties: {
    unit: {
      check: "String",
      nullable: false
    }
  },

  members: {
    // overridden
    _getContentHtml: function(cellInfo) {
      if (cellInfo.value == null || cellInfo.value < 0) { // eslint-disable-line no-eq-null
        return "";
      }
      return `${cellInfo.value} ${this.getUnit()}`;
    }
  }
});
