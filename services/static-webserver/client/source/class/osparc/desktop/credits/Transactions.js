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

  members: {
    __table: null,

    __buildLayout: function() {
      const tableModel = new qx.ui.table.model.Simple();
      tableModel.setColumns([
        this.tr("Date"),
        this.tr("Credits"),
        this.tr("Price"),
        this.tr("Wallet"),
        this.tr("Comment")
      ]);

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
