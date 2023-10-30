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

/**
  * Both, usage and transactions, mixed
  */

qx.Class.define("osparc.desktop.credits.ActivityTable", {
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
    columnModel.getBehavior().setWidth(cols.invoice.pos, 60);

    columnModel.setDataCellRenderer(cols.credits.pos, new qx.ui.table.cellrenderer.Number());

    if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.setColumnVisible(cols.invoice.pos, false);
    }
  },

  statics: {
    COLUMNS: {
      date: {
        pos: 0,
        title: qx.locale.Manager.tr("Date")
      },
      type: {
        pos: 1,
        title: qx.locale.Manager.tr("Type")
      },
      title: {
        pos: 2,
        title: qx.locale.Manager.tr("Title")
      },
      credits: {
        pos: 3,
        title: qx.locale.Manager.tr("Credits")
      },
      invoice: {
        pos: 4,
        title: qx.locale.Manager.tr("Invoice")
      }
    },

    createPdfIconWithLink: function(link) {
      return `<a href='${link}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    },

    usagesToActivities: function(usages) {
      const activities = [];
      usages.forEach(usage => {
        const activity = {
          date: usage["started_at"],
          type: "Usage",
          title: usage["project_name"],
          credits: usage["credit_cost"],
          invoice: ""
        };
        activities.push(activity);
      });
      return activities;
    },

    transactionsToActivities: function(transactions) {
      const activities = [];
      transactions.forEach(transaction => {
        const activity = {
          date: transaction["createdAt"],
          type: "Transaction",
          title: transaction["comment"] ? transaction["comment"] : "",
          credits: transaction["osparcCredits"].toFixed(2),
          invoice: transaction["invoice"]
        };
        activities.push(activity);
      });
      return activities;
    },

    respDataToTableRow: function(data) {
      const cols = this.COLUMNS;
      const newData = [];
      newData[cols["date"].pos] = osparc.utils.Utils.formatDateAndTime(new Date(data["date"]));
      newData[cols["type"].pos] = data["type"];
      newData[cols["credits"].pos] = data["credits"] ? data["credits"] : "-";
      const invoiceUrl = data["invoice"];
      newData[cols["invoice"].pos] = invoiceUrl? this.createPdfIconWithLink(invoiceUrl) : "";
      return newData;
    },

    respDataToTableData: function(datas) {
      const newDatas = [];
      if (datas) {
        for (const data of datas) {
          const newData = this.respDataToTableRow(data);
          newDatas.push(newData);
        }
      }
      return newDatas;
    }
  },

  members: {
    addData: function(datas) {
      const newDatas = this.self().respDataToTableData(datas);
      this.setData(newDatas);
    }
  }
});
