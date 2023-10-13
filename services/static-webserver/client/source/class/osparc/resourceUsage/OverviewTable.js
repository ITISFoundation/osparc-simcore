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

qx.Class.define("osparc.resourceUsage.OverviewTable", {
  extend: osparc.ui.table.Table,

  construct: function() {
    const model = this.__model = new qx.ui.table.model.Simple();
    const cols = this.self().COLUMNS;
    const colNames = [];
    Object.entries(cols).forEach(([key, data]) => {
      if (key === "wallet" && !osparc.desktop.credits.Utils.areWalletsEnabled()) {
        return;
      }
      colNames.push(data.title);
    });
    model.setColumns(colNames);

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false
    });
    this.makeItLoose();

    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setWidth(this.self().COLUMNS.duration.pos, 60);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.status.pos, 70);
    if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.getBehavior().setWidth(this.self().COLUMNS.wallet.pos, 100);
    }
    columnModel.getBehavior().setWidth(this.self().COLUMNS.cost.pos, 60);
  },

  statics: {
    COLUMNS: {
      project: {
        pos: 0,
        title: osparc.product.Utils.getStudyAlias({firstUpperCase: true})
      },
      node: {
        pos: 1,
        title: qx.locale.Manager.tr("Node")
      },
      service: {
        pos: 2,
        title: qx.locale.Manager.tr("Service")
      },
      start: {
        pos: 3,
        title: qx.locale.Manager.tr("Start")
      },
      duration: {
        pos: 4,
        title: qx.locale.Manager.tr("Duration")
      },
      status: {
        pos: 5,
        title: qx.locale.Manager.tr("Status")
      },
      wallet: {
        pos: 6,
        title: qx.locale.Manager.tr("Credit Account")
      },
      cost: {
        pos: 7,
        title: qx.locale.Manager.tr("Cost")
      }
    },

    respDataToTableData: function(datas) {
      const newDatas = [];
      if (datas) {
        const cols = this.COLUMNS;
        datas.forEach(data => {
          const newData = [];
          newData[cols["project"].pos] = data["project_name"] ? data["project_name"] : data["project_id"];
          newData[cols["node"].pos] = data["node_name"] ? data["node_name"] : data["node_id"];
          if (data["service_key"]) {
            const parts = data["service_key"].split("/");
            const serviceName = parts.pop();
            newData[cols["service"].pos] = serviceName + ":" + data["service_version"];
          }
          if (data["started_at"]) {
            const startTime = new Date(data["started_at"]);
            newData[cols["start"].pos] = osparc.utils.Utils.formatDateAndTime(startTime);
            if (data["stopped_at"]) {
              const stopTime = new Date(data["stopped_at"]);
              const durationTime = stopTime - startTime;
              newData[cols["duration"].pos] = osparc.utils.Utils.formatMilliSeconds(durationTime);
            }
          }
          newData[cols["status"].pos] = qx.lang.String.firstUp(data["service_run_status"].toLowerCase());
          if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
            newData[cols["wallet"].pos] = data["wallet_name"] ? data["wallet_name"] : "-";
          }
          newData[cols["cost"].pos] = data["credit_cost"] ? data["credit_cost"] : "-";
          newDatas.push(newData);
        });
      }
      return newDatas;
    }
  },

  members: {
    __model: null,

    addData: function(datas) {
      const newDatas = this.self().respDataToTableData(datas);
      this.setData(newDatas);
    }
  }
});
