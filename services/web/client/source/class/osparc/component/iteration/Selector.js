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

qx.Class.define("osparc.component.iteration.Selector", {
  extend: qx.ui.table.Table,

  construct: function(primaryStudy) {
    this.__primaryStudy = primaryStudy;

    const model = this.__model = this.__initModel();

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });

    this.__initTable();
    this.__populateTable();
  },

  statics: {
    popUpInWindow: function(selectorWidget) {
      const window = new osparc.ui.window.Window(qx.locale.Manager.tr("Iteration Selector")).set({
        autoDestroy: true,
        layout: new qx.ui.layout.Grow(),
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        width: 400,
        height: 400,
        clickAwayClose: true
      });
      window.add(selectorWidget);
      window.center();
      window.open();
      return window;
    }
  },

  events: {
    "openIteration": "qx.event.type.Data"
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
      },
      "variables": {
        col: 2,
        label: qx.locale.Manager.tr("Variables")
      },
      "show": {
        col: 3,
        label: qx.locale.Manager.tr("Show")
      }
    },

    __initModel: function() {
      const model = new qx.ui.table.model.Simple();
      const cols = [];
      Object.keys(this.__cols).forEach(colKey => {
        cols.push(this.__cols[colKey].label);
      });
      model.setColumns(cols);
      return model;
    },

    __initTable: function() {
      const columnModel = this.getTableColumnModel();
      columnModel.getBehavior().setMinWidth(this.__cols["name"].col, 120);
      columnModel.getBehavior().setMinWidth(this.__cols["variables"].col, 120);
      columnModel.getBehavior().setMinWidth(this.__cols["show"].col, 50);

      this.getSelectionModel().setSelectionMode(qx.ui.table.selection.Model.SINGLE_SELECTION);
    },

    __populateTable: function() {
      const secStudyIds = this.__primaryStudy.getSweeper().getSecondaryStudyIds();
      const rows = [];
      Object.keys(secStudyIds).forEach(secStudyId => {
        const secStudy = secStudyIds[secStudyId];
        const row = [];
        row[this.__cols["id"].col] = secStudy["uuid"];
        row[this.__cols["name"].col] = secStudy["name"];
        row[this.__cols["variables"].col] = "";
        const loadStudyBtn = new qx.ui.form.Button(this.tr("Load Study"));
        loadStudyBtn.addListener("execute", () => {
          this.fireDataEvent("openIteration", secStudy["uuid"]);
        }, this);
        row[this.__cols["show"].col] = loadStudyBtn;
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    }
  }
});
