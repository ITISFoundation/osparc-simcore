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

qx.Class.define("osparc.desktop.credits.TransactionsTable", {
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

    const columnModel = this.getTableColumnModel();
    columnModel.setDataCellRenderer(cols.credits.pos, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(cols.status.pos, new qx.ui.table.cellrenderer.Html());
    columnModel.setDataCellRenderer(cols.invoice.pos, new qx.ui.table.cellrenderer.Html());
    this.setColumnWidth(cols.invoice.pos, 50);
    this.makeItLoose();
  },

  statics: {
    COLUMNS: {
      date: {
        pos: 0,
        title: qx.locale.Manager.tr("Date")
      },
      price: {
        pos: 1,
        title: qx.locale.Manager.tr("Price USD")
      },
      credits: {
        pos: 2,
        title: qx.locale.Manager.tr("Credits")
      },
      status: {
        pos: 3,
        title: qx.locale.Manager.tr("Status")
      },
      comment: {
        pos: 4,
        title: qx.locale.Manager.tr("Comment")
      },
      invoice: {
        pos: 5,
        title: qx.locale.Manager.tr("Invoice")
      }
    },

    addColorTag: function(status) {
      const color = this.getLevelColor(status);
      status = osparc.utils.Utils.onlyFirstsUp(status);
      return ("<font color=" + color +">" + status + "</font>");
    },

    getLevelColor: function(status) {
      const colorManager = qx.theme.manager.Color.getInstance();
      let logLevel = null;
      switch (status) {
        case "SUCCESS":
          logLevel = "info";
          break;
        case "PENDING":
          logLevel = "warning";
          break;
        case "CANCELED":
        case "FAILED":
          logLevel = "error";
          break;
        default:
          console.error("completedStatus unknown");
          break;
      }
      return colorManager.resolve("logger-"+logLevel+"-message");
    },

    createPdfIconWithLink: function(link) {
      return `<a href='${link}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    },

    respDataToTableRow: function(data) {
      const cols = this.COLUMNS;
      const newData = [];
      newData[cols["date"].pos] = osparc.utils.Utils.formatDateAndTime(new Date(data["createdAt"]));
      newData[cols["price"].pos] = data["priceDollars"] ? data["priceDollars"].toFixed(2) : 0;
      newData[cols["credits"].pos] = data["osparcCredits"] ? data["osparcCredits"].toFixed(2) : 0;
      if (data["completedStatus"]) {
        newData[cols["status"].pos] = this.addColorTag(data["completedStatus"]);
      }
      newData[cols["comment"].pos] = data["comment"];
      const invoiceUrl = data["invoiceUrl"];
      newData[cols["invoice"].pos] = invoiceUrl? this.createPdfIconWithLink(invoiceUrl) : "";

      return newData;
    },

    respDataToTableData: function(datas) {
      const newDatas = [];
      if (datas) {
        datas.forEach(data => {
          const newData = this.respDataToTableRow(data);
          newDatas.push(newData);
        });
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
