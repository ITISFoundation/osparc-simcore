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

qx.Class.define("osparc.desktop.credits.Transactions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__buildLayout();
  },

  statics: {
    COLUMNS: {
      date: {
        pos: 0,
        title: qx.locale.Manager.tr("Date")
      },
      credits: {
        pos: 1,
        title: qx.locale.Manager.tr("Credits")
      },
      price: {
        pos: 2,
        title: qx.locale.Manager.tr("Price")
      },
      wallet: {
        pos: 3,
        title: qx.locale.Manager.tr("Wallet")
      },
      comment: {
        pos: 4,
        title: qx.locale.Manager.tr("Comment")
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
          const startTime = new Date(data["started_at"]);
          newData[cols["start"].pos] = osparc.utils.Utils.formatDateAndTime(startTime);
          const stopTime = new Date(data["stopped_at"]);
          const durationTimeSec = (stopTime - startTime)/1000;
          newData[cols["duration"].pos] = durationTimeSec;
          newData[cols["status"].pos] = qx.lang.String.firstUp(data["service_run_status"].toLowerCase());
          newData[cols["wallet"].pos] = data["wallet_label"] ? data["wallet_label"] : "unknown";
          newData[cols["cost"].pos] = "unknown";
          newDatas.push(newData);
        });
      }
      return newDatas;
    }
  },

  members: {
    __table: null,

    __buildLayout: function() {
      const tableModel = new qx.ui.table.model.Simple();
      const cols = this.self().COLUMNS;
      const colNames = Object.values(cols).map(col => col.title);
      tableModel.setColumns(colNames);

      const table = this.__table = new osparc.ui.table.Table(tableModel, {
        tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj)
      });
      table.setColumnWidth(0, 100);
      table.setColumnWidth(1, 100);
      table.makeItLoose();
      this._add(table);

      this.__rawData = [];

      // welcome
      this.addRow(
        20,
        0,
        "My Wallet",
        "Welcome to Sim4Life"
      );

      // one payment
      this.addRow(
        50,
        125,
        "My Wallet",
        ""
      );
    },

    addRow: function(nCredits, price, walletName, comment) {
      const newData = [
        osparc.utils.Utils.formatDateAndTime(new Date()),
        nCredits ? nCredits : 0,
        price ? price : 0,
        walletName ? walletName : "Unknown Wallet",
        comment ? comment : ""
      ];
      this.__rawData.push(newData);
      this.__table.setData(this.__rawData);
    }
  }
});
