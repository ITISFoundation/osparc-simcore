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

qx.Class.define("osparc.component.snapshots.Snapshots", {
  extend: osparc.ui.table.Table,

  construct: function(study) {
    this.__study = study;

    const model = this.__initModel();

    this.base(arguments, model, {
      initiallyHiddenColumns: [
        this.self().T_POS.ID.col
      ],
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.TAGS.col, 100);
    this.setColumnWidth(this.self().T_POS.MESSAGE.col, 150);
    this.setColumnWidth(this.self().T_POS.DATE.col, 130);

    this.__populateSnapshotsTable();
  },

  statics: {
    T_POS: {
      ID: {
        col: 0,
        label: "Id"
      },
      TAGS: {
        col: 1,
        label: qx.locale.Manager.tr("Tags")
      },
      MESSAGE: {
        col: 2,
        label: qx.locale.Manager.tr("Message")
      },
      DATE: {
        col: 3,
        label: qx.locale.Manager.tr("Created At")
      }
    }
  },

  members: {
    __study: null,

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

    __populateSnapshotsTable: function() {
      const columnModel = this.getTableColumnModel();
      columnModel.setDataCellRenderer(this.self().T_POS.ID.col, new qx.ui.table.cellrenderer.Number());
      columnModel.setDataCellRenderer(this.self().T_POS.TAGS.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.MESSAGE.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.DATE.col, new qx.ui.table.cellrenderer.Date());

      this.__study.getSnapshots()
        .then(snapshots => {
          const rows = [];
          snapshots.forEach(snapshot => {
            const row = [];
            row[this.self().T_POS.ID.col] = snapshot["id"];
            row[this.self().T_POS.TAGS.col] = snapshot["tags"].join(", ");
            row[this.self().T_POS.MESSAGE.col] = snapshot["message"];
            const date = new Date(snapshot["created_at"]);
            row[this.self().T_POS.DATE.col] = osparc.utils.Utils.formatDateAndTime(date);
            rows.push(row);
          });
          this.getTableModel().setData(rows, false);
        });
    }
  }
});
