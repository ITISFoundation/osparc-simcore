/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.snapshots.Iterations", {
  extend: osparc.ui.table.Table,

  construct: function() {
    const model = this.__initModel();

    this.base(arguments, model, {
      initiallyHiddenColumns: [
        this.self().T_POS.ID.col
      ],
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.NAME.col, 100);
  },

  statics: {
    T_POS: {
      ID: {
        col: 0,
        label: "Id"
      },
      NAME: {
        col: 1,
        label: qx.locale.Manager.tr("Name")
      }
    }
  },

  members: {
    getRowData: function(rowIdx) {
      return this.getTableModel().getRowDataAsMap(rowIdx);
    },

    __initModel: function() {
      const model = new qx.ui.table.model.Simple();

      const cols = [];
      Object.keys(this.self().T_POS).forEach(colKey => {
        const idx = this.self().T_POS[colKey].col;
        const label = this.self().T_POS[colKey].label;
        cols.splice(idx, 0, label);
      });
      model.setColumns(cols);

      return model;
    },

    setSelection: function(iterationId) {
      this.resetSelection();
      for (let i=0; i<this.getTableModel().getRowCount(); i++) {
        if (this.getRowData(i)["Id"] === iterationId) {
          this.getSelectionModel().setSelectionInterval(i, i);
          return;
        }
      }
    },

    populateTable: function(iterations) {
      const columnModel = this.getTableColumnModel();
      columnModel.setDataCellRenderer(this.self().T_POS.ID.col, new qx.ui.table.cellrenderer.Number());
      columnModel.setDataCellRenderer(this.self().T_POS.NAME.col, new qx.ui.table.cellrenderer.String());

      const rows = [];
      iterations.forEach(iteration => {
        const row = [];
        row[this.self().T_POS.ID.col] = iteration["id"];
        row[this.self().T_POS.NAME.col] = iteration["name"];
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    }
  }
});
