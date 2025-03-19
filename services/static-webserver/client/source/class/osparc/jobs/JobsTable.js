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


qx.Class.define("osparc.jobs.JobsTable", {
  extend: qx.ui.table.Table,

  construct: function(filters) {
    this.base(arguments);

    const model = new osparc.jobs.JobsTableModel(filters);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.JOB_ID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));
  },

  statics: {
    COLS: {
      JOB_ID: {
        id: "jobId",
        column: 0,
        label: qx.locale.Manager.tr("JobId"),
        width: 150
      },
      SOLVER: {
        id: "solver",
        column: 1,
        label: qx.locale.Manager.tr("Solver"),
        width: 150
      },
      STATUS: {
        id: "status",
        column: 2,
        label: qx.locale.Manager.tr("Status"),
        width: 150
      },
      PROGRESS: {
        id: "progress",
        column: 3,
        label: qx.locale.Manager.tr("Progress"),
        width: 100
      },
      SUBMIT: {
        id: "submit",
        column: 4,
        label: qx.locale.Manager.tr("Submitted"),
        width: 150
      },
      START: {
        id: "start",
        column: 5,
        label: qx.locale.Manager.tr("Started"),
        width: 150
      },
      INSTANCE: {
        id: "instance",
        column: 6,
        label: qx.locale.Manager.tr("Instance"),
        width: 150
      },
    }
  }
});
