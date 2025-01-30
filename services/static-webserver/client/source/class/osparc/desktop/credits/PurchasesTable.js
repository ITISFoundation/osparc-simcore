/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.desktop.credits.PurchasesTable", {
  extend: qx.ui.table.Table,

  construct: function(walletId, filters) {
    this.base(arguments);

    const model = new osparc.desktop.credits.PurchasesTableModel(walletId, filters);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.PURCHASE_ID.column, false);
    columnModel.setColumnVisible(this.self().COLS.ITEM_ID.column, false);
    columnModel.setDataCellRenderer(this.self().COLS.COST.column, new qx.ui.table.cellrenderer.Number());

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));
  },

  statics: {
    COLS: {
      PURCHASE_ID: {
        id: "purchaseId",
        column: 0,
        label: qx.locale.Manager.tr("PurchaseId"),
        width: 150
      },
      ITEM_ID: {
        id: "itemId",
        column: 1,
        label: qx.locale.Manager.tr("ItemId"),
        width: 150
      },
      ITEM_LABEL: {
        id: "itemLabel",
        column: 2,
        label: qx.locale.Manager.tr("Name"),
        width: 150
      },
      START: {
        id: "start",
        column: 3,
        label: qx.locale.Manager.tr("Start"),
        width: 150
      },
      END: {
        id: "end",
        column: 4,
        label: qx.locale.Manager.tr("End"),
        width: 150
      },
      SEATS: {
        id: "seats",
        column: 5,
        label: qx.locale.Manager.tr("Seats"),
        width: 50
      },
      COST: {
        id: "cost",
        column: 6,
        label: qx.locale.Manager.tr("Credits"),
        width: 60
      },
      USER: {
        id: "user",
        column: 7,
        label: qx.locale.Manager.tr("User"),
        width: 100
      },
    }
  }
});
