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


qx.Class.define("osparc.jobs.ClustersTable", {
  extend: qx.ui.table.Table,

  construct: function(filters) {
    this.base(arguments);

    const model = new osparc.jobs.ClustersTableModel(filters);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.CLUSTER_ID.column, true);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));
  },

  statics: {
    COLS: {
      CLUSTER_ID: {
        id: "clusterId",
        column: 0,
        label: qx.locale.Manager.tr("Cluster Id"),
        width: 280
      },
      NAME: {
        id: "name",
        column: 1,
        label: qx.locale.Manager.tr("Name"),
        width: 100
      },
      STATUS: {
        id: "status",
        column: 2,
        label: qx.locale.Manager.tr("Status"),
        width: 170
      },
      N_WORKERS: {
        id: "nWorkers",
        column: 3,
        label: qx.locale.Manager.tr("# Workers"),
        width: 80
      },
    }
  },
});
