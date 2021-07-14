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

    this.setColumnWidth(this.self().T_POS.NAME.col, 200);
    this.setColumnWidth(this.self().T_POS.DATE.col, 120);

    // this.__populateTable();
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
        label: qx.locale.Manager.tr("Created at")
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

      // add data-iterators to columns
      const nextCol = Object.keys(this.__cols).length;
      const iterators = this.__primaryStudy.getIterators();
      for (let i=0; i<iterators.length; i++) {
        const dataIterator = iterators[i];
        this.__cols[dataIterator.getNodeId()] = {
          col: nextCol+i,
          label: dataIterator.getLabel()
        };
      }

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
              row[this.__cols["id"].col] = secondaryStudy.uuid;
              row[this.__cols["name"].col] = secondaryStudy.name;
              const date = row[this.__cols["createdAt"].col] = new Date(secondaryStudy.creationDate);
              row[this.__cols["createdAt"].col] = osparc.utils.Utils.formatDateAndTime(date);
              // OM: hack for demo for
              row[Object.keys(this.__cols).length] = i+1;
              rows.push(row);
            }
            this.getTableModel().setData(rows, false);
          });
      }
    }
  }
});
