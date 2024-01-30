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

    // const model = new qx.ui.table.model.Simple();
    // const cols = this.self().COLUMNS;
    // const colNames = Object.values(cols).map(col => col.title);
    // model.setColumns(colNames);

    // this.base(arguments, model, {
    //   tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
    //   statusBarVisible: false
    // });
    // this.makeItLoose();

    // const columnModel = this.getTableColumnModel();
    // columnModel.getBehavior().setWidth(cols.duration.pos, 70);
    // columnModel.getBehavior().setWidth(cols.status.pos, 70);
    // columnModel.getBehavior().setWidth(cols.cost.pos, 60);

    // columnModel.setDataCellRenderer(cols.cost.pos, new qx.ui.table.cellrenderer.Number());

    // if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
    //   columnModel.setColumnVisible(cols.cost.pos, false);
    //   columnModel.setColumnVisible(cols.user.pos, false);
    // }
  }
})
