/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * String cell renderer that does not override the cell styles.
 */
qx.Class.define("osparc.ui.table.cellrenderer.String", {
  extend: qx.ui.table.cellrenderer.String,
  construct: function() {
    this.base(arguments);
  },
  members: {
    // Override
    _getCellStyle: function(cellInfo) {
      const baseStyle = this.base(arguments, cellInfo) || "";
      const cellStyle = cellInfo.style || "";
      return baseStyle + cellStyle;
    }
  }
});
