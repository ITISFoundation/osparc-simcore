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

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;

    const model = this.__initModel();

    this.base(arguments, model, {
      initiallyHiddenColumns: [
        this.self().T_POS.STUDY_ID.col,
        this.self().T_POS.SNAPSHOT_ID.col,
        this.self().T_POS.PARENT_ID.col
      ],
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.NAME.col, 220);
    this.setColumnWidth(this.self().T_POS.DATE.col, 130);

    this.__populateSnapshotsTable();
  },

  statics: {
    T_POS: {
      STUDY_ID: {
        col: 0,
        label: "StudyId"
      },
      NAME: {
        col: 1,
        label: qx.locale.Manager.tr("Snapshot Name")
      },
      DATE: {
        col: 2,
        label: qx.locale.Manager.tr("Created At")
      },
      SNAPSHOT_ID: {
        col: 3,
        label: "SnapshotId"
      },
      PARENT_ID: {
        col: 4,
        label: "ParentId"
      }
    }
  },

  members: {
    __primaryStudy: null,

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
      columnModel.setDataCellRenderer(this.self().T_POS.STUDY_ID.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.NAME.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.DATE.col, new qx.ui.table.cellrenderer.Date());
      columnModel.setDataCellRenderer(this.self().T_POS.SNAPSHOT_ID.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.PARENT_ID.col, new qx.ui.table.cellrenderer.String());

      this.__primaryStudy.getSnapshots()
        .then(snapshots => {
          const rows = [];
          snapshots.reverse().forEach(snapshot => {
            const row = [];
            row[this.self().T_POS.STUDY_ID.col] = snapshot["project_uuid"];
            row[this.self().T_POS.NAME.col] = snapshot["label"];
            const date = new Date(snapshot["created_at"]);
            row[this.self().T_POS.DATE.col] = osparc.utils.Utils.formatDateAndTime(date);
            row[this.self().T_POS.SNAPSHOT_ID.col] = snapshot["id"];
            row[this.self().T_POS.PARENT_ID.col] = snapshot["parent_uuid"];
            rows.push(row);
          });
          this.getTableModel().setData(rows, false);
        });
    }
  }
});
