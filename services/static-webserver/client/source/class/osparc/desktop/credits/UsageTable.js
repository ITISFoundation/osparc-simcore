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

qx.Class.define("osparc.desktop.credits.UsageTable", {
  extend: osparc.ui.table.Table,

  construct: function() {
    const model = new qx.ui.table.model.Simple();
    const cols = this.self().COLUMNS;
    const colNames = Object.values(cols).map(col => col.title);
    model.setColumns(colNames);

    this.base(arguments, model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      statusBarVisible: false
    });
    this.makeItLoose();

    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setWidth(this.self().COLUMNS.duration.pos, 70);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.status.pos, 70);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.wallet.pos, 100);
    columnModel.getBehavior().setWidth(this.self().COLUMNS.cost.pos, 60);

    if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.setColumnVisible(this.self().COLUMNS.wallet.pos, false);
      columnModel.setColumnVisible(this.self().COLUMNS.user.pos, false);
    }
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
      },
      user: {
        pos: 8,
        title: qx.locale.Manager.tr("User")
      }
    },

    respDataToTableRow: async function(data) {
      const cols = this.COLUMNS;
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
      newData[cols["wallet"].pos] = data["wallet_name"] ? data["wallet_name"] : "-";
      newData[cols["cost"].pos] = data["credit_cost"] ? data["credit_cost"] : "-";
      const user = await osparc.store.Store.getInstance().getUser(data["user_id"]);
      if (user) {
        newData[cols["user"].pos] = user ? user["label"] : data["user_id"];
      }
      return newData;
    },

    respDataToTableData: async function(datas) {
      const newDatas = [];
      if (datas) {
        for (const data of datas) {
          const newData = await this.respDataToTableRow(data);
          newDatas.push(newData);
        }
      }
      return newDatas;
    }
  },

  members: {
    addData: async function(datas) {
      const newDatas = await this.self().respDataToTableData(datas);
      this.setData(newDatas);
    }
  }
});
