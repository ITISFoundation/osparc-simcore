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
    this.setHeaderCellHeight(26);
    this.setRowHeight(26);

    // this.base(arguments, model, {
    //   tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
    //   statusBarVisible: false
    // });

    const columnModel = this.getTableColumnModel();

    columnModel.setColumnWidth(4, 70);
    columnModel.setColumnWidth(5, 70);
    columnModel.setColumnWidth(6, 60);

    columnModel.setDataCellRenderer(6, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(7, new qx.ui.table.cellrenderer.Number());

    if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
      columnModel.setColumnVisible(6, false);
      columnModel.setColumnVisible(7, false);
    }
  }
})
