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

qx.Class.define("osparc.desktop.credits.TransactionsTable", {
  extend: qx.ui.table.Table,

  construct: function() {
    this.base(arguments)
    const model = new osparc.desktop.credits.TransactionsTableModel();
    this.setTableModel(model)
    this.setStatusBarVisible(false)

    const columnModel = this.getTableColumnModel();

    columnModel.setDataCellRenderer(2, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(3, new qx.ui.table.cellrenderer.Html());
    columnModel.setDataCellRenderer(5, new qx.ui.table.cellrenderer.Html());
    this.setColumnWidth(5, 50);

    this.setHeaderCellHeight(26);
    this.setRowHeight(26);
  }
});
