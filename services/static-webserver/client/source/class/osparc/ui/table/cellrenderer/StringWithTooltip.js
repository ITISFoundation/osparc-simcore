/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.table.cellrenderer.StringWithTooltip", {
  extend: qx.ui.table.cellrenderer.Default,
  members: {
    // overridden
    _getCellAttributes(cellInfo) {
      const attrs = this.base(arguments, cellInfo)
      return `${attrs} title="${cellInfo.value}"`
    }
  }
})
