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
    model.setColumns(colNames);

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false
    });
    this.makeItLoose();

    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setWidth(this.self().COLUMNS.duration.pos, 60);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.processors.pos, 80);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.coreHours.pos, 80);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.status.pos, 70);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.wallet.pos, 80);
    columnModel.setDataCellRenderer(this.self().COLUMNS.duration.pos, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(this.self().COLUMNS.processors.pos, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(this.self().COLUMNS.coreHours.pos, new qx.ui.table.cellrenderer.Number());
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
      },
      wallet: {
        pos: 8,
        title: "Wallet"
      }
    }
  },

  members: {
    __model: null,

    addData: function(datas) {
      const newDatas = [];
      if (datas) {
        const cols = this.self().COLUMNS;
        datas.forEach(data => {
          const newData = [];
          newData[cols["project"].pos] = data["project_name"] ? data["project_name"] : data["project_uuid"];
          newData[cols["node"].pos] = data["node_label"] ? data["node_label"] : data["node_uuid"];
          if (data["service_key"]) {
            const parts = data["service_key"].split("/");
            const serviceName = parts.pop();
            newData[cols["service"].pos] = serviceName + ":" + data["service_version"];
          }
          newData[cols["start"].pos] = osparc.utils.Utils.formatDateAndTime(new Date(data["start_time"]));
          newData[cols["duration"].pos] = data["duration"];
          newData[cols["processors"].pos] = data["processors"];
          newData[cols["coreHours"].pos] = data["core_hours"];
          newData[cols["status"].pos] = qx.lang.String.firstUp(data["status"]);
          newData[cols["wallet"].pos] = data["wallet_label"] ? data["wallet_label"] : "Wallet ID?";
          newDatas.push(newData);
        });
      }
      this.setData(newDatas);
    }
  }
});
