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
    const model = this.__model = this.__initModel(primaryStudy);

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
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

    __initModel: function(primaryStudy) {
      const model = new qx.ui.table.model.Simple();
      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        cols.push(this.__cols[colKey].label);
      });
      // add variables in columns

      model.setColumns(cols);
      return model;
    }
  }
});
