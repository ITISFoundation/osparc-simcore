/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.resourceUsage.OverviewTable", {
  extend: osparc.ui.table.Table,

  construct: function() {
    const cols = this.self().COLUMNS;
    const model = this.__model = new qx.ui.table.model.Simple();
    const colNames = Object.values(cols).map(col => col.title);
    console.log(colNames);
    model.setColumns(colNames);

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj)
    });
    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setMinWidth(1, 80);
    columnModel.getBehavior().setMinWidth(2, 80);
  },

  statics: {
    COLUMNS: {
      project: {
        pos: 0,
        title: "Project"
      },
      node: {
        pos: 1,
        title: "Node"
      },
      service: {
        pos: 2,
        title: "Service"
      },
      start: {
        pos: 3,
        title: "Start"
      },
      duration: {
        pos: 4,
        title: "Duration"
      },
      processors: {
        pos: 5,
        title: "Processors"
      },
      coreHours: {
        pos: 6,
        title: "Core Hours"
      },
      status: {
        pos: 7,
        title: "Status"
      }
    }
  },

  members: {
    __model: null,

    setData: function(data) {
      console.log("data", data);
    }
  }
});
