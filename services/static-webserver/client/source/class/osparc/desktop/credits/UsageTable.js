/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.UsageTable", {
  extend: qx.ui.table.Table,

  construct: function(walletId, filters) {
    this.base(arguments)
    const model = new osparc.desktop.credits.UsageTableModel(walletId, filters)
    this.setTableModel(model)
    this.setStatusBarVisible(false)

    this.setHeaderCellHeight(26);
    this.setRowHeight(26);

    const columnModel = this.getTableColumnModel();

    columnModel.setDataCellRenderer(6, new qx.ui.table.cellrenderer.Number());

    if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.setColumnVisible(6, false);
      columnModel.setColumnVisible(7, false);
    }
    columnModel.setColumnVisible(2, false)

    // Array [0, 1, ..., N] where N is column_count - 1 (default column order)
    this.__columnOrder = [...Array(columnModel.getOverallColumnCount()).keys()]

    if (
      osparc.Preferences.getInstance().getBillingCenterUsageColumnOrder() &&
      osparc.Preferences.getInstance().getBillingCenterUsageColumnOrder().length === this.__columnOrder.length
    ) {
      columnModel.setColumnsOrder(osparc.Preferences.getInstance().getBillingCenterUsageColumnOrder())
      this.__columnOrder = osparc.Preferences.getInstance().getBillingCenterUsageColumnOrder()
    } else {
      osparc.Preferences.getInstance().setBillingCenterUsageColumnOrder(this.__columnOrder)
    }

    columnModel.addListener("orderChanged", e => {
      // Save new order into preferences
      if (e.getData()) {
        const { fromOverXPos, toOverXPos } = e.getData()
        // Edit current order
        this.__columnOrder = this.__columnOrder.toSpliced(toOverXPos, 0, this.__columnOrder.splice(fromOverXPos, 1)[0])
        // Save order
        osparc.Preferences.getInstance().setBillingCenterUsageColumnOrder(this.__columnOrder)
      }
    }, this)

    columnModel.setColumnWidth(0, 130)
    columnModel.setColumnWidth(1, 130)
    columnModel.setColumnWidth(3, 130)
    columnModel.setColumnWidth(4, 70)
    columnModel.setColumnWidth(5, 70)
    columnModel.setColumnWidth(6, 56)
    columnModel.setColumnWidth(7, 130)
  },

  statics: {
    COLS: {
      PROJECT: {
        id: "project",
        column: 0,
        label: osparc.product.Utils.getStudyAlias({firstUpperCase: true}),
        width: 130
      },
      NODE: {
        id: "node",
        column: 1,
        label: qx.locale.Manager.tr("Node"),
        width: 130
      },
      SERVICE: {
        id: "service",
        column: 2,
        label: qx.locale.Manager.tr("Service"),
        width: 130
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
        id: "project",
        column: 7,
        label: qx.locale.Manager.tr("User"),
        width: 130
      }
    }
  }
});
