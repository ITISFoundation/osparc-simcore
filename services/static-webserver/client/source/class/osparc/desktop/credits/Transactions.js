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
      price: {
        pos: 1,
        title: qx.locale.Manager.tr("Price")
      },
      credits: {
        pos: 2,
        title: qx.locale.Manager.tr("Credits")
      },
      wallet: {
        pos: 3,
        title: qx.locale.Manager.tr("Credit Account")
      },
      status: {
        pos: 4,
        title: qx.locale.Manager.tr("Status")
      },
      comment: {
        pos: 5,
        title: qx.locale.Manager.tr("Comment")
      },
      invoice: {
        pos: 6,
        title: qx.locale.Manager.tr("Invoice")
      }
    },

    createPdfIconWithLink: function(link) {
      return `<a href='${link}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    },

    respDataToTableData: function(datas) {
      const newDatas = [];
      if (datas) {
        const cols = this.COLUMNS;
        datas.forEach(data => {
          const newData = [];
          newData[cols["date"].pos] = osparc.utils.Utils.formatDateAndTime(new Date(data["createdAt"]));
          newData[cols["price"].pos] = data["priceDollars"] ? data["priceDollars"] : 0;
          newData[cols["credits"].pos] = data["osparcCredits"] ? data["osparcCredits"] : 0;
          let walletName = "Unknown";
          const found = osparc.desktop.credits.Utils.getWallet(data["walletId"]);
          if (found) {
            walletName = found.getName();
          }
          newData[cols["wallet"].pos] = walletName;
          newData[cols["status"].pos] = osparc.utils.Utils.onlyFirstsUp(data["completedStatus"]);
          newData[cols["comment"].pos] = data["comment"];
          newData[cols["invoice"].pos] = this.createPdfIconWithLink(data["invoiceUrl"] ? data["invoiceUrl"] : "https://assets.website-files.com/63206faf68ab2dc3ee3e623b/634ea60a9381021f775e7a28_Placeholder%20PDF.pdf");
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
      const imageRenderer = new qx.ui.table.cellrenderer.Html();
      table.getTableColumnModel().setDataCellRenderer(cols.invoice.pos, imageRenderer);
      table.setColumnWidth(cols.invoice.pos, 50);
      table.makeItLoose();
      this._add(table);

      this.refetchData();
    },

    refetchData: function() {
      this.__table.setData([]);
      osparc.data.Resources.fetch("payments", "get")
        .then(transactions => {
          if ("data" in transactions) {
            const newDatas = this.self().respDataToTableData(transactions["data"]);
            this.__table.setData(newDatas);
          }
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    }
  }
});
