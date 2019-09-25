/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a table display the status of running services in real time. Simulates, in some cases, the behavior of a tree.
 * Has sorting and resizing capabilities, and its UI changes depending on its display mode, that changes depending on the activated type of sorting.
 * WiP
 */
qx.Class.define("qxapp.component.service.manager.ActivityTree", {
  extend: qx.ui.table.Table,

  /**
   * Constructor sets the model and general look.
   */
  construct: function(data) {
    this.__model = new qx.ui.table.model.Simple();
    this.__model.setColumns([
      "Type",
      "Node",
      "Service",
      "Status",
      "CPU usage",
      "GPU usage"
    ]);
    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });
    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setMinWidth(1, 80);
    columnModel.getBehavior().setMinWidth(2, 80);

    // React to filter changes
    const msgName = qxapp.utils.Utils.capitalize("activityMonitor", "filter");
    qx.event.message.Bus.getInstance().subscribe(msgName, msg => this.__applyFilter(msg), this);
  },

  properties: {
    mode: {
      check: "String",
      nullable: false,
      init: "hierarchical",
      apply: "_applyMode"
    },
    data: {
      check: "Array",
      apply: "_applyData"
    }
  },

  statics: {
    modes: {
      HIERARCHICAL: "hierarchical",
      FLAT: "flat"
    }
  },

  members: {
    __model: null,

    _applyMode: function(mode) {
      const columnModel = this.getTableColumnModel();
      switch (mode) {
        case this.self().modes.HIERARCHICAL:
          columnModel.setDataCellRenderer(1,
            new qx.ui.table.cellrenderer.Dynamic(cellInfo => {
              if (cellInfo.rowData[0] === qxapp.component.service.manager.ActivityManager.itemTypes.SERVICE) {
                return new qxapp.ui.table.cellrenderer.Indented(1);
              }
              return new qxapp.ui.table.cellrenderer.Indented(0);
            })
          );
          break;
        case this.self().modes.ONLY_SERVICES:
          columnModel.setDataCellRenderer(1, new qx.ui.table.cellrenderer.Default());
          break;
      }
    },

    __applyFilter: function(msg) {
      const filterText = msg.getData().name;
      const filterStudy = msg.getData().study;
      // Filtering function
      const filter = row => {
        // By text
        const nameFilterFn = roww => {
          if (roww[0] === qxapp.component.service.manager.ActivityManager.itemTypes.STUDY) {
            return true;
          }
          const name = roww[1];
          if (filterText.length > 1) {
            return name.trim().toLowerCase()
              .includes(filterText.trim().toLowerCase());
          }
          return true;
        };
        // By study
        const studyFilterFn = roww => {
          return true;
        };
        // Compose functions (AND)
        return nameFilterFn(row) && studyFilterFn(row);
      };
      // Apply filters
      const filteredData = this.getData().filter(row => filter(row));
      this.getTableModel().setData(this.__removeEmptyStudies(filteredData));
    },

    __removeEmptyStudies: function(data) {
      return data.filter((item, index, array) => {
        if (item[0] === qxapp.component.service.manager.ActivityManager.itemTypes.STUDY) {
          if (index === array.length-1) {
            return false;
          }
          if (item[0] === array[index+1][0]) {
            return false;
          }
        }
        return true;
      });
    },

    _applyData: function(data) {
      this._applyMode(this.getMode());
      this.getTableModel().setData(data);
    }
  }
});
