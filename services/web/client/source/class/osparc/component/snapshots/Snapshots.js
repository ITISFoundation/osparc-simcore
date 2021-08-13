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

    this.__cols = {};
    const model = this.__initModel();

    this.base(arguments, model, {
      initiallyHiddenColumns: [this.self().T_POS.ID.col],
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.NAME.col, 220);
    this.setColumnWidth(this.self().T_POS.DATE.col, 130);

    // this.__populateTable();
    this.__populateSnapshotsTable();
  },

  statics: {
    T_POS: {
      ID: {
        col: 0,
        label: qx.locale.Manager.tr("StudyId")
      },
      NAME: {
        col: 1,
        label: qx.locale.Manager.tr("Snapshot Name")
      },
      DATE: {
        col: 2,
        label: qx.locale.Manager.tr("Created At")
      },
      PARAMETERS: {
        col: 3,
        label: qx.locale.Manager.tr("Parameters")
      },
      ACTIONS: {
        col: 4,
        label: ""
      }
    }
  },

  members: {
    __primaryStudy: null,
    __cols: null,

    getRowData: function(rowIdx) {
      return this.getTableModel().getRowDataAsMap(rowIdx);
    },

    __initModel: function() {
      const model = new qx.ui.table.model.Simple();

      Object.keys(this.self().T_POS).forEach(colKey => {
        this.__cols[colKey] = this.self().T_POS[colKey];
      });

      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        const idx = this.__cols[colKey].col;
        const label = this.__cols[colKey].label;
        cols.splice(idx, 0, label);
      });
      model.setColumns(cols);

      return model;
    },

    __populateTable: function() {
      const columnModel = this.getTableColumnModel();
      const initCols = Object.keys(this.self().T_POS).length;
      const totalCols = Object.keys(this.__cols).length;
      for (let i=initCols; i<totalCols; i++) {
        columnModel.setDataCellRenderer(i, new qx.ui.table.cellrenderer.Number());
      }

      const combinations = this.__primaryStudy.getSweeper().getCombinations();
      const secondaryStudyIds = this.__primaryStudy.getSweeper().getSecondaryStudyIds();
      if (combinations.length === secondaryStudyIds.length) {
        osparc.data.Resources.get("studies", null, false)
          .then(studies => {
            const rows = [];
            for (let i=0; i<secondaryStudyIds.length; i++) {
              const secondaryStudyId = secondaryStudyIds[i];
              const secondaryStudy = studies.find(study => study.uuid === secondaryStudyId);
              if (!secondaryStudy) {
                console.error("Secondary study not found", secondaryStudyId);
                continue;
              }
              const row = [];
              row[this.self().T_POS.ID.col] = secondaryStudy.uuid;
              row[this.self().T_POS.NAME.col] = secondaryStudy.name;
              const date = new Date(secondaryStudy.creationDate);
              row[this.self().T_POS.DATE.col] = osparc.utils.Utils.formatDateAndTime(date);
              row[this.self().T_POS.ACTIONS.col] = new qx.ui.form.Button();
              rows.push(row);
            }
            this.getTableModel().setData(rows, false);
          });
      }
    },

    __populateSnapshotsTable: function() {
      const columnModel = this.getTableColumnModel();
      const initCols = Object.keys(this.self().T_POS).length;
      const totalCols = Object.keys(this.__cols).length;
      for (let i=initCols; i<totalCols; i++) {
        columnModel.setDataCellRenderer(i, new qx.ui.table.cellrenderer.Number());
      }

      osparc.data.model.Study.getSnapshots()
        .then(snapshots => {
          const rows = [];
          snapshots.reverse().forEach(snapshot => {
            const row = [];
            row[this.self().T_POS.ID.col] = snapshot["7aed0b07-99a9-3552-9126-ed05b508e9f5"];
            row[this.self().T_POS.NAME.col] = snapshot["label"];
            const date = new Date(snapshot["created_at"]);
            row[this.self().T_POS.DATE.col] = osparc.utils.Utils.formatDateAndTime(date);
            // row[this.self().T_POS.ACTIONS.col] = new qx.ui.form.Button();
            rows.push(row);
          });
          this.getTableModel().setData(rows, false);
        });
    }
  }
});
