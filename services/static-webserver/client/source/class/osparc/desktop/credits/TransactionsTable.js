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

    columnModel.setColumnWidth(0, 130);
    columnModel.setColumnWidth(1, 70);
    columnModel.setColumnWidth(2, 70);
    columnModel.setColumnWidth(3, 75);
    columnModel.setColumnWidth(4, 320);
    columnModel.setColumnWidth(5, 60);

    columnModel.setDataCellRenderer(1, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(2, new qx.ui.table.cellrenderer.Number());
    columnModel.setDataCellRenderer(3, new qx.ui.table.cellrenderer.Html());
    columnModel.setDataCellRenderer(4, new osparc.ui.table.cellrenderer.StringWithTooltip());
    columnModel.setDataCellRenderer(5, new qx.ui.table.cellrenderer.Html());

    this.setHeaderCellHeight(26);
    this.setRowHeight(26);
  }
});
