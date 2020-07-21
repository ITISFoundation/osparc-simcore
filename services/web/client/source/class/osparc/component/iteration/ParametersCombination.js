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

      // https://stackoverflow.com/questions/15298912/javascript-generating-combinations-from-n-arrays-with-m-elements
      const cartesian = args => {
      // const cartesian = (...args) => {
        const r = [];
        const max = args.length-1;
        const helper = (arr, i) => {
          for (let j=0, l=args[i].length; j<l; j++) {
            const a = arr.slice(0); // clone arr
            a.push(args[i][j]);
            if (i === max) {
              r.push(a);
            } else {
              helper(a, i+1);
            }
          }
        };
        helper([], 0);
        return r;
      };

      const rows = [];
      if (arrs.length) {
        const combs = cartesian(arrs);
        let combId = 0;
        for (let i=0; i<combs.length; i++) {
          const comb = combs[i];
          const row = [];
          row[this.__cols["id"].col] = combId++;
          row[this.__cols["name"].col] = "Iteration " + combId;
          for (let j=0; j<comb.length; j++) {
            row[this.__cols["name"].col+1+j] = comb[j];
          }
          rows.push(row);
        }
      }
      this.getTableModel().setData(rows, false);
    }
  }
});
