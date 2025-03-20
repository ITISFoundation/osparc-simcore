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
    columnModel.setColumnVisible(this.self().COLS.JOB_ID.column, true);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const fontButtonRenderer = new osparc.ui.table.cellrenderer.ImageButtonRenderer();
    fontButtonRenderer.setIconPath("osparc/circle-info-solid_text.svg");
    columnModel.setDataCellRenderer(this.self().COLS.INFO.column, fontButtonRenderer);
  },

  statics: {
    COLS: {
      JOB_ID: {
        id: "jobId",
        column: 0,
        label: qx.locale.Manager.tr("Job Id"),
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
        width: 170
      },
      PROGRESS: {
        id: "progress",
        column: 3,
        label: qx.locale.Manager.tr("Progress"),
        width: 80
      },
      SUBMIT: {
        id: "submit",
        column: 4,
        label: qx.locale.Manager.tr("Submitted"),
        width: 130
      },
      START: {
        id: "start",
        column: 5,
        label: qx.locale.Manager.tr("Started"),
        width: 130
      },
      INSTANCE: {
        id: "instance",
        column: 6,
        label: qx.locale.Manager.tr("Instance"),
        width: 90
      },
      INFO: {
        id: "info",
        column: 7,
        label: qx.locale.Manager.tr("Info"),
        width: 40
      },
    }
  }
});
