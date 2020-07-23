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

qx.Class.define("osparc.component.iteration.ParametersCombination", {
  extend: osparc.ui.table.Table,

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;

    this.__initModel();

    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
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
      this.__primaryStudy.getParameters().forEach(parameter => {
        cols.push(parameter.label);
      });

      model.setColumns(cols);

      return model;
    },

    __updateTable: function() {
      const params = this.__primaryStudy.getParameters();
      const steps = osparc.data.StudyParametrizer.calculateSteps(params);
      this.__primaryStudy.setSteps(steps);

      const rows = [];
      const combinations = this.__primaryStudy.getCombinations();
      const secondaryStudies = this.__primaryStudy.getSecondaryStudies();
      if (combinations.length === secondaryStudies.length) {
        for (let i=0; i<combinations.length; i++) {
          const comb = combinations[i];
          const row = [];
          row[this.__cols["id"].col] = secondaryStudies[i].id;
          row[this.__cols["name"].col] = secondaryStudies[i].name;
          const nextCol = this.__cols["name"].col + 1;
          for (let j=0; j<comb.length; j++) {
            row[nextCol+j] = comb[j];
          }
          rows.push(row);
        }
      }
      this.getTableModel().setData(rows, false);
    }
  }
});
