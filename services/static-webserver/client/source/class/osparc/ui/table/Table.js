/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Qooxdoo's table widget with some convenient methods.
 */
qx.Class.define("osparc.ui.table.Table", {
  extend: qx.ui.table.Table,

  properties: {
    data: {
      check: "Array",
      apply: "_applyData"
    }
  },

  members: {
    getSelection: function() {
      const ret = [];
      const selectionRanges = this.getSelectionModel().getSelectedRanges();
      if (selectionRanges.length > 0) {
        selectionRanges.forEach(range => {
          for (let i=range.minIndex; i<=range.maxIndex; i++) {
            ret.push(this.getTableModel().getRowData(i));
          }
        });
      }
      return ret;
    },

    _applyData: function(data) {
      this.getTableModel().setData(data, false);
    },

    makeItLoose: function() {
      this.setHeaderCellHeight(26);
      this.setRowHeight(26);
    }
  }
});
