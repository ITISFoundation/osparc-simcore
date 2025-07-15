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

  construct: function(collectionRunId) {
    this.base(arguments);

    const model = new osparc.jobs.SubRunsTableModel(collectionRunId);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.COLLECTION_RUN_ID.column, false);
    columnModel.setColumnVisible(this.self().COLS.NODE_ID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const iconPathInfo = "osparc/icons/circle-info-text.svg";
    const fontButtonRendererInfo = new osparc.ui.table.cellrenderer.ImageButtonRenderer("info", iconPathInfo);
    columnModel.setDataCellRenderer(this.self().COLS.INFO.column, fontButtonRendererInfo);

    const iconPathLogs = "osparc/icons/file-download-text.svg";
    const fontButtonRendererLogs = new osparc.ui.table.cellrenderer.ImageButtonRenderer("logs", iconPathLogs);
    columnModel.setDataCellRenderer(this.self().COLS.LOGS.column, fontButtonRendererLogs);

    this.__attachHandlers();
  },

  statics: {
    COLS: {
      COLLECTION_RUN_ID: {
        id: "collectionRunId",
        column: 0,
        label: qx.locale.Manager.tr("Collection Run Id"),
        width: 200
      },
      NODE_ID: {
        id: "nodeId",
        column: 1,
        label: qx.locale.Manager.tr("Node Id"),
        width: 200
      },
      NAME: {
        id: "name",
        column: 2,
        label: qx.locale.Manager.tr("Name"),
        width: 100
      },
      APP: {
        id: "app",
        column: 3,
        label: qx.locale.Manager.tr("App"),
        width: 100
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
        width: 130,
        sortableMap: "started_at",
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
      CREDITS: {
        id: "credits",
        column: 9,
        label: qx.locale.Manager.tr("Credits"),
        width: 70
      },
      INFO: {
        id: "info",
        column: 10,
        label: qx.locale.Manager.tr("Info"),
        width: 40
      },
      LOGS: {
        id: "logs",
        column: 11,
        label: qx.locale.Manager.tr("Logs"),
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
      this.resetSelection();
       // In order to make the button tappable again, the cell needs to be unfocused (blurred)
      this.resetCellFocus();
      const rowData = this.getTableModel().getRowData(row);
      switch (action) {
        case "info": {
          const job = osparc.store.Jobs.getInstance().getJob(rowData["collectionRunId"]);
          if (!job) {
            return;
          }
          const subJob = job.getSubJob(rowData["nodeId"]);
          if (!subJob) {
            return;
          }
          const jobInfo = new osparc.jobs.Info(subJob.getImage());
          const win = osparc.jobs.Info.popUpInWindow(jobInfo);
          win.setCaption(rowData["name"]);
          break;
        }
        case "logs": {
          const job = osparc.store.Jobs.getInstance().getJob(rowData["collectionRunId"]);
          if (!job) {
            return;
          }
          const subJob = job.getSubJob(rowData["nodeId"]);
          if (!subJob) {
            return;
          }
          const logDownloadLink = subJob.getLogDownloadLink()
          if (logDownloadLink) {
            osparc.utils.Utils.downloadLink(logDownloadLink, "GET", rowData["name"] + ".zip");
          } else {
            osparc.FlashMessenger.logAs(this.tr("No logs available"), "WARNING");
          }
          break;
        }
        default:
          console.warn(`Unknown action: ${action}`);
          break;
      }
    },
  }
});
