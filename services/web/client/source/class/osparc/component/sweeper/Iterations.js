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

qx.Class.define("osparc.component.sweeper.Iterations", {
  extend: osparc.ui.table.Table,

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;

    this.__initModel();

    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false,
      initiallyHiddenColumns: [0]
    });

    this.__updateTable();
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    __primaryStudy: null,
    __model: null,

    __cols: {
      "id": {
        col: 0,
        label: qx.locale.Manager.tr("StudyId")
      },
      "name": {
        col: 1,
        label: qx.locale.Manager.tr("Iteration")
      }
    },

    getRowData: function(rowIdx) {
      return this.__model.getRowDataAsMap(rowIdx);
    },

    __cleanupCols: function() {
      Object.keys(this.__cols).forEach(key => {
        if (!["id", "name"].includes(key)) {
          delete this.__cols[key];
        }
      });
    },

    __initModel: function() {
      const model = this.__model = new qx.ui.table.model.Simple();

      // add variables in columns
      const parameters = this.__primaryStudy.getSweeper().getParameters();
      this.__cleanupCols();
      const nextCol = this.__cols["name"].col + 1;
      for (let i=0; i<parameters.length; i++) {
        const parameter = parameters[i];
        this.__cols[parameter.id] = {
          col: nextCol+i,
          label: parameter.label
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

    __updateTable: function() {
      const columnModel = this.getTableColumnModel();
      for (let i=2; i<Object.keys(this.__cols).length; i++) {
        columnModel.setDataCellRenderer(i, new qx.ui.table.cellrenderer.Number());
      }

      const combinations = this.__primaryStudy.getSweeper().getCombinations();
      const secondaryStudyIds = this.__primaryStudy.getSweeper().getSecondaryStudyIds();
      if (combinations.length === secondaryStudyIds.length) {
        osparc.data.Resources.get("studies")
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
              const paramValues = secondaryStudy["dev"]["sweeper"]["parameterValues"];
              paramValues.forEach(paramValue => {
                for (const [key, value] of Object.entries(paramValue)) {
                  row[this.__cols[key].col] = value;
                }
              });
              rows.push(row);
            }
            this.getTableModel().setData(rows, false);
          });
      }
    }
  }
});
