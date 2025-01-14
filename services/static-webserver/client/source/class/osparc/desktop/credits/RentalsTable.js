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


qx.Class.define("osparc.desktop.credits.RentalsTable", {
  extend: qx.ui.table.Table,

  construct: function(walletId, filters) {
    this.base(arguments)
    const model = new osparc.desktop.credits.RentalsTableModel(walletId, filters)
    this.setTableModel(model)
    this.setStatusBarVisible(false)

    this.setHeaderCellHeight(26);
    this.setRowHeight(26);

    const columnModel = this.getTableColumnModel();

    columnModel.setDataCellRenderer(this.self().COLS.COST.column, new qx.ui.table.cellrenderer.Number());

    if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.setColumnVisible(this.self().COLS.COST.column, false);
      columnModel.setColumnVisible(this.self().COLS.USER.column, false);
    }
    columnModel.setColumnVisible(this.self().COLS.SERVICE.column, false);

    // Array [0, 1, ..., N] where N is column_count - 1 (default column order)
    this.__columnOrder = [...Array(columnModel.getOverallColumnCount()).keys()]

    if (
      osparc.Preferences.getInstance().getBillingCenterRentalsColumnOrder() &&
      osparc.Preferences.getInstance().getBillingCenterRentalsColumnOrder().length === this.__columnOrder.length
    ) {
      columnModel.setColumnsOrder(osparc.Preferences.getInstance().getBillingCenterRentalsColumnOrder())
      this.__columnOrder = osparc.Preferences.getInstance().getBillingCenterRentalsColumnOrder()
    } else {
      osparc.Preferences.getInstance().setBillingCenterRentalsColumnOrder(this.__columnOrder)
    }

    columnModel.addListener("orderChanged", e => {
      // Save new order into preferences
      if (e.getData()) {
        const { fromOverXPos, toOverXPos } = e.getData()
        // Edit current order
        this.__columnOrder = this.__columnOrder.toSpliced(toOverXPos, 0, this.__columnOrder.splice(fromOverXPos, 1)[0])
        // Save order
        osparc.Preferences.getInstance().setBillingCenterRentalsColumnOrder(this.__columnOrder)
      }
    }, this)

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));
  },

  statics: {
    COLS: {
      PROJECT: {
        id: "project",
        column: 0,
        label: osparc.product.Utils.getStudyAlias({firstUpperCase: true}),
        width: 140
      },
      NODE: {
        id: "node",
        column: 1,
        label: qx.locale.Manager.tr("Node"),
        width: 140
      },
      SERVICE: {
        id: "service",
        column: 2,
        label: qx.locale.Manager.tr("Service"),
        width: 140
      },
      START: {
        id: "start",
        column: 3,
        label: qx.locale.Manager.tr("Start"),
        width: 130
      },
      DURATION: {
        id: "duration",
        column: 4,
        label: qx.locale.Manager.tr("Duration"),
        width: 70
      },
      STATUS: {
        id: "status",
        column: 5,
        label: qx.locale.Manager.tr("Status"),
        width: 70
      },
      COST: {
        id: "cost",
        column: 6,
        label: qx.locale.Manager.tr("Credits"),
        width: 56
      },
      USER: {
        id: "user",
        column: 7,
        label: qx.locale.Manager.tr("User"),
        width: 140
      },
      TAGS: {
        id: "tags",
        column: 7,
        label: qx.locale.Manager.tr("Tags"),
        width: 140
      },
    }
  }
});
