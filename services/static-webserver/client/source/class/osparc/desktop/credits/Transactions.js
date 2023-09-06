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
        title: qx.locale.Manager.tr("Wallet")
      },
      comment: {
        pos: 4,
        title: qx.locale.Manager.tr("Comment")
      },
      invoice: {
        pos: 5,
        title: qx.locale.Manager.tr("Invoice")
      }
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
      this.__rawData = [];

      osparc.data.Resources.fetch("payments", "get")
        .then(transactions => {
          if ("data" in transactions) {
            transactions["data"].forEach(transaction => {
              let walletName = null;
              if (transaction["walletId"]) {
                const found = osparc.desktop.credits.Utils.getWallet(transaction["walletId"]);
                if (found) {
                  walletName = found.getName();
                }
              }
              this.__addRow(
                transaction["createdAt"],
                transaction["priceDollars"],
                transaction["osparcCredits"],
                walletName,
                transaction["comment"],
                "https://assets.website-files.com/63206faf68ab2dc3ee3e623b/634ea60a9381021f775e7a28_Placeholder%20PDF.pdf"
              );
            });
          }
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __createPdfIconWithLink: function(link) {
      return `<a href='${link}' target='_blank'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/PDF_file_icon.svg/833px-PDF_file_icon.svg.png' alt='Invoice' width='16' height='20'></a>`;
    },

    __addRow: function(createdAt, price, nCredits, walletName, comment, invoiceUrl) {
      const newData = [
        osparc.utils.Utils.formatDateAndTime(new Date(createdAt)),
        price ? price : 0,
        nCredits ? nCredits : 0,
        walletName ? walletName : "Unknown Wallet",
        comment ? comment : "",
        invoiceUrl ? this.__createPdfIconWithLink(invoiceUrl) : null
      ];
      this.__rawData.push(newData);
      this.__table.setData(this.__rawData);
    }
  }
});
