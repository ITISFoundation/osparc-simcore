/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.sweeper.FileSweepers", {
  extend: osparc.ui.table.Table,

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;
    const model = this.__initModel();

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false,
      initiallyHiddenColumns: [0]
    });

    this.__initTable();
    this.updateTable();
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    __model: null,

    __cols: {
      "id": {
        col: 0,
        label: qx.locale.Manager.tr("Id")
      },
      "label": {
        col: 1,
        label: qx.locale.Manager.tr("Name")
      },
      "nFiles": {
        col: 2,
        label: qx.locale.Manager.tr("#Files")
      }
    },

    __initModel: function() {
      const model = this.__model = new qx.ui.table.model.Simple();

      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        cols.push(this.__cols[colKey].label);
      });
      model.setColumns(cols);

      return model;
    },

    __initTable: function() {
      const cols = this.__cols;

      const model = this.__model;
      model.setColumnEditable(cols["id"].col, false);
      model.setColumnEditable(cols["label"].col, false);
      model.setColumnEditable(cols["nFiles"].col, false);

      this.getSelectionModel().setSelectionMode(qx.ui.table.selection.Model.SINGLE_SELECTION);
    },

    updateTable: function() {
      const fileSweepers = osparc.data.StudyFileSweeper.getFileSweepers(this.__primaryStudy.serializeStudy());

      const rows = [];
      fileSweepers.forEach(fileSweeper => {
        const row = [];
        row[this.__cols["id"].col] = fileSweeper["id"];
        row[this.__cols["label"].col] = fileSweeper["label"];
        row[this.__cols["nFiles"].col] = fileSweeper["outputs"]["outFiles"].length;
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    }
  }
});
