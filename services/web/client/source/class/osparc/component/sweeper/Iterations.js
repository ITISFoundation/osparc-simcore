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

    __initModel: function() {
      const model = this.__model = new qx.ui.table.model.Simple();

      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        cols.push(this.__cols[colKey].label);
      });
      // add variables in columns
      this.__primaryStudy.getSweeper().getParameters().forEach(parameter => {
        cols.push(parameter.label);
      });

      model.setColumns(cols);

      return model;
    },

    __updateTable: function() {
      const combinations = this.__primaryStudy.getSweeper().getCombinations();
      const secondaryStudyIds = this.__primaryStudy.getSweeper().getSecondaryStudyIds();
      if (combinations.length === secondaryStudyIds.length) {
        osparc.store.Store.getInstance().getStudiesWState(true)
          .then(studies => {
            const rows = [];
            for (let i=0; i<secondaryStudyIds.length; i++) {
              const secondaryStudyId = secondaryStudyIds[i];
              const secondaryStudy = studies.find(study => study.uuid === secondaryStudyId);
              if (!secondaryStudy) {
                console.error("Secondary study not found", secondaryStudyId);
                continue;
              }
              const comb = combinations[i];
              const row = [];
              row[this.__cols["id"].col] = secondaryStudy.uuid;
              row[this.__cols["name"].col] = secondaryStudy.name;
              const nextCol = this.__cols["name"].col + 1;
              for (let j=0; j<comb.length; j++) {
                row[nextCol+j] = comb[j];
              }
              rows.push(row);
            }
            this.getTableModel().setData(rows, false);
          });
      }
    }
  }
});
