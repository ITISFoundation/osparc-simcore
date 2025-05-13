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


qx.Class.define("osparc.jobs.SubRunsTable", {
  extend: qx.ui.table.Table,

  construct: function(projectUuid) {
    this.base(arguments);

    const model = new osparc.jobs.SubRunsTableModel(projectUuid);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.PROJECT_UUID.column, false);
    columnModel.setColumnVisible(this.self().COLS.NODE_ID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const iconPathInfo = "osparc/circle-info-text.svg";
    const fontButtonRendererInfo = new osparc.ui.table.cellrenderer.ImageButtonRenderer("info", iconPathInfo);
    columnModel.setDataCellRenderer(this.self().COLS.IMAGE.column, fontButtonRendererInfo);

    this.__attachHandlers();
  },

  statics: {
    COLS: {
      PROJECT_UUID: {
        id: "projectUuid",
        column: 0,
        label: qx.locale.Manager.tr("Project Id"),
        width: 170
      },
      NODE_ID: {
        id: "nodeId",
        column: 1,
        label: qx.locale.Manager.tr("Node Id"),
        width: 170
      },
      NODE_NAME: {
        id: "nodeName",
        column: 2,
        label: qx.locale.Manager.tr("Node"),
        width: 170
      },
      SOLVER: {
        id: "solver",
        column: 3,
        label: qx.locale.Manager.tr("Solver"),
        width: 150
      },
      STATE: {
        id: "state",
        column: 4,
        label: qx.locale.Manager.tr("Status"),
        width: 100
      },
      PROGRESS: {
        id: "progress",
        column: 5,
        label: qx.locale.Manager.tr("Progress"),
        width: 70
      },
      START: {
        id: "start",
        column: 6,
        label: qx.locale.Manager.tr("Started"),
        width: 130
      },
      END: {
        id: "end",
        column: 7,
        label: qx.locale.Manager.tr("Ended"),
        width: 130
      },
      DURATION: {
        id: "duration",
        column: 8,
        label: qx.locale.Manager.tr("Duration"),
        width: 70
      },
      IMAGE: {
        id: "image",
        column: 9,
        label: qx.locale.Manager.tr("Info"),
        width: 40
      },
    }
  },

  members: {
    reloadSubRuns: function() {
      const model = this.getTableModel();
      model.reloadData();
    },

    __attachHandlers: function() {
      this.addListener("cellTap", e => {
        const row = e.getRow();
        const target = e.getOriginalTarget();
        if (target.closest(".qx-material-button") && (target.tagName === "IMG" || target.tagName === "DIV")) {
          const action = target.closest(".qx-material-button").getAttribute("data-action");
          if (action) {
            this.__handleButtonClick(action, row);
          }
        }
      });
    },

    __handleButtonClick: function(action, row) {
      const rowData = this.getTableModel().getRowData(row);
      switch (action) {
        case "info": {
          const job = osparc.store.Jobs.getInstance().getJob(rowData["projectUuid"]);
          if (!job) {
            return;
          }
          const subJob = job.getSubJob(rowData["nodeId"]);
          if (!subJob) {
            return;
          }
          const jobInfo = new osparc.jobs.Info(subJob.getImage());
          const win = osparc.jobs.Info.popUpInWindow(jobInfo);
          win.setCaption(rowData["nodeName"]);
          break;
        }
        default:
          console.warn(`Unknown action: ${action}`);
          break;
      }
    },
  }
});
