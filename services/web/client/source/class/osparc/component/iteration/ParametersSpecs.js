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

/**
 *
 */

qx.Class.define("osparc.component.iteration.ParametersSpecs", {
  extend: osparc.ui.table.Table,

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;
    const model = this.__initModel();

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false,
      initiallyHiddenColumns: [0]
    });

    this.__initTable();
    this.updateTable();
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    __model: null,

    __cols: {
      "id": {
        col: 0,
        label: qx.locale.Manager.tr("Id")
      },
      "label": {
        col: 1,
        label: qx.locale.Manager.tr("Name")
      },
      "low": {
        col: 2,
        label: qx.locale.Manager.tr("Low")
      },
      "high": {
        col: 3,
        label: qx.locale.Manager.tr("High")
      },
      "steps": {
        col: 4,
        label: qx.locale.Manager.tr("Steps")
      },
      "distribution": {
        col: 5,
        label: qx.locale.Manager.tr("Distribution")
      }
    },

    __initModel: function() {
      const model = this.__model = new qx.ui.table.model.Simple();

      model.addListener("dataChanged", e => {
        const data = e.getData();
        if (data.firstColumn === data.lastColumn && data.firstRow === data.lastRow) {
          const rowData = model.getRowData(data.firstRow);
          this.__dataChanged(rowData);
        }
      });

      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        cols.push(this.__cols[colKey].label);
      });
      model.setColumns(cols);

      return model;
    },

    __initTable: function() {
      const model = this.__model;
      const cols = this.__cols;
      model.setColumnEditable(cols["id"].col, false);
      model.setColumnEditable(cols["label"].col, true);
      model.setColumnEditable(cols["low"].col, true);
      model.setColumnEditable(cols["high"].col, true);
      model.setColumnEditable(cols["steps"].col, true);
      model.setColumnEditable(cols["distribution"].col, false);

      this.getSelectionModel().setSelectionMode(qx.ui.table.selection.Model.SINGLE_SELECTION);
    },

    updateTable: function() {
      const parameters = this.__primaryStudy.getSweeper().getParameters();

      const rows = [];
      parameters.forEach(parameter => {
        const row = [];
        row[this.__cols["id"].col] = parameter["id"];
        row[this.__cols["label"].col] = parameter["label"];
        row[this.__cols["low"].col] = parameter["low"];
        row[this.__cols["high"].col] = parameter["high"];
        row[this.__cols["steps"].col] = parameter["steps"];
        row[this.__cols["distribution"].col] = parameter["distribution"];
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    },

    __dataChanged: function(rowData) {
      const cols = this.__cols;
      const parameters = this.__primaryStudy.getSweeper().getParameters();
      const idx = parameters.findIndex(existingParam => existingParam.id === rowData[cols["id"].col]);
      if (idx !== -1) {
        const parameter = parameters[idx];
        parameter.label = rowData[cols["label"].col];
        parameter.low = rowData[cols["low"].col];
        parameter.high = rowData[cols["high"].col];
        parameter.steps = rowData[cols["steps"].col];
      }
    }
  }
});
