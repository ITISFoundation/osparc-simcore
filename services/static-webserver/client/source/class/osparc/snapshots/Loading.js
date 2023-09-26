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

qx.Class.define("osparc.snapshots.Loading", {
  extend: osparc.ui.table.Table,

  construct: function(resourceName) {
    const model = this.__initModel();

    this.base(arguments, model, {
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.NAME.col, 200);

    this.__populateTable(resourceName);
  },

  statics: {
    T_POS: {
      NAME: {
        col: 0,
        label: qx.locale.Manager.tr("Name")
      }
    }
  },

  members: {

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

    __populateTable: function(resourceName) {
      const columnModel = this.getTableColumnModel();
      columnModel.setDataCellRenderer(this.self().T_POS.NAME.col, new qx.ui.table.cellrenderer.String());

      const rows = [];
      const row = [];
      row[this.self().T_POS.NAME.col] = this.tr("Loading ") + resourceName + "...";
      rows.push(row);

      this.getTableModel().setData(rows, false);
    }
  }
});
