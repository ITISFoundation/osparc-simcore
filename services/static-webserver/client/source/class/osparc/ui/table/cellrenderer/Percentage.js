/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.table.cellrenderer.Percentage", {
  extend: qx.ui.table.cellrenderer.Html,

  construct: function(color) {
    this.base(arguments, "center");
    this.setColor(color);
  },

  properties: {
    color: {
      check: "String",
      nullable: false
    },
    unit: {
      check: "String",
      nullable: false,
      init: "%"
    }
  },

  members: {
    // overridden
    _getContentHtml: function(cellInfo) {
      if (cellInfo.value == null || cellInfo.value < 0) {
        return "";
      }
      const splitted = cellInfo.value.split("/");
      const width = typeof parseFloat(splitted[0]) === "number" && splitted.length === 2 ? this._calculateWidthPercentage(splitted[0], splitted[1]) : 0;
      return "" +
        `<div style="position: absolute; left: 0; right: 0;">${splitted[0]} ${this.getUnit()}</div>` +
        `<div style="height: 100%; width: ${width}%; background-color: ${this.getColor()};"></div>`;
    },

    _calculateWidthPercentage: function(value, limit) {
      return (value / limit) * 100;
    }
  }
});
