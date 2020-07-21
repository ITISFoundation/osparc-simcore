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
      const arrs = [];
      const params = this.__primaryStudy.getParameters();
      params.forEach(param => {
        const arr = [];
        const step = param.steps > 1 ? ((param.high - param.low) / (param.steps-1)) : 0;
        for (let i=0; i<param.steps; i++) {
          arr.push(param.low + step*i);
        }
        arrs.push(arr);
      });
      console.log(arrs);

      const getLinearCombination = (arr, pre) => {
        pre = pre || "";
        if (!arr.length) {
          return pre;
        }
        const ans = arr[0].reduce((ans2, value) => {
          return ans2.concat(getLinearCombination(arr.slice(1), pre + value));
        }, []);
        return ans;
      };

      console.log(getLinearCombination(arrs));
    }
  }
});
