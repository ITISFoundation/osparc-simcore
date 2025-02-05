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


qx.Class.define("osparc.desktop.credits.CheckoutsTable", {
  extend: qx.ui.table.Table,

  construct: function(walletId, filters) {
    this.base(arguments);

    const model = new osparc.desktop.credits.CheckoutsTableModel(walletId, filters);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.CHECKOUT_ID.column, false);
    columnModel.setColumnVisible(this.self().COLS.ITEM_ID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));
  },

  statics: {
    COLS: {
      CHECKOUT_ID: {
        id: "checkoutId",
        column: 0,
        label: qx.locale.Manager.tr("CheckoutId"),
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
      DURATION: {
        id: "duration",
        column: 4,
        label: qx.locale.Manager.tr("Duration"),
        width: 150
      },
      SEATS: {
        id: "seats",
        column: 5,
        label: qx.locale.Manager.tr("Seats"),
        width: 50
      },
      USER: {
        id: "user",
        column: 6,
        label: qx.locale.Manager.tr("User"),
        width: 150
      },
    }
  }
});
