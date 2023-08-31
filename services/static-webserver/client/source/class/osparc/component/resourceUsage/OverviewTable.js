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
    columnModel.getBehavior().setWidth(this.self().COLUMNS.status.pos, 70);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.wallet.pos, 80);
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
      status: {
        pos: 5,
        title: "Status"
      },
      wallet: {
        pos: 6,
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
          newData[cols["project"].pos] = data["project_name"] ? data["project_name"] : data["project_id"];
          newData[cols["node"].pos] = data["node_name"] ? data["node_name"] : data["node_id"];
          if (data["service_key"]) {
            const parts = data["service_key"].split("/");
            const serviceName = parts.pop();
            newData[cols["service"].pos] = serviceName + ":" + data["service_version"];
          }
          const startTime = new Date(data["started_at"]);
          newData[cols["start"].pos] = osparc.utils.Utils.formatDateAndTime(startTime);
          const stopTime = new Date(data["stopped_at"]);
          const durationTimeSec = (stopTime - startTime)/1000;
          newData[cols["duration"].pos] = durationTimeSec;
          newData[cols["status"].pos] = qx.lang.String.firstUp(data["service_run_status"].toLowerCase());
          newData[cols["wallet"].pos] = data["wallet_label"] ? data["wallet_label"] : "unknown";
          newDatas.push(newData);
        });
      }
      this.setData(newDatas);
    }
  }
});
