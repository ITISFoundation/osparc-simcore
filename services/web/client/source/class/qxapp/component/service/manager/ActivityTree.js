/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.service.manager.ActivityTree", {
  extend: qx.ui.table.Table,

  construct: function() {
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
    columnModel.setDataCellRenderer(1,
      new qx.ui.table.cellrenderer.Dynamic(cellInfo => {
        if (cellInfo.rowData[0] === qxapp.component.service.manager.ActivityManager.itemTypes.SERVICE) {
          return new qxapp.ui.table.cellrenderer.Indented(1);
        }
        return new qxapp.ui.table.cellrenderer.Indented(0);
      })
    );
  },

  properties: {
    mode: {
      check: "String",
      nullable: false,
      init: "default"
    }
  },

  statics: {
    modes: {
      DEFAULT: "default"
    }
  },

  members: {
    __model: null
  }
});
