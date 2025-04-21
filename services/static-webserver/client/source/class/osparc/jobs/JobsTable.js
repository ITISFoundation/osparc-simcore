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
    columnModel.setColumnVisible(this.self().COLS.PROJECT_UUID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const iconPathInfo = "osparc/circle-info-text.svg";
    const fontButtonRendererInfo = new osparc.ui.table.cellrenderer.ImageButtonRenderer("info", iconPathInfo);
    columnModel.setDataCellRenderer(this.self().COLS.INFO.column, fontButtonRendererInfo);

    const iconPathStop = "osparc/circle-stop-text.svg";
    const fontButtonRendererStop = new osparc.ui.table.cellrenderer.ImageButtonRenderer("stop", iconPathStop);
    columnModel.setDataCellRenderer(this.self().COLS.ACTION_STOP.column, fontButtonRendererStop);

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
      PROJECT_NAME: {
        id: "projectName",
        column: 1,
        label: qx.locale.Manager.tr("Project Name"),
        width: 170,
        sortable: true
      },
      STATE: {
        id: "state",
        column: 2,
        label: qx.locale.Manager.tr("State"),
        width: 170
      },
      SUBMIT: {
        id: "submit",
        column: 3,
        label: qx.locale.Manager.tr("Submitted"),
        width: 130,
        sortable: true
      },
      START: {
        id: "start",
        column: 4,
        label: qx.locale.Manager.tr("Started"),
        width: 130,
        sortable: true
      },
      END: {
        id: "end",
        column: 5,
        label: qx.locale.Manager.tr("Ended"),
        width: 130,
        sortable: true
      },
      INFO: {
        id: "info",
        column: 6,
        label: qx.locale.Manager.tr("Info"),
        width: 40
      },
      ACTION_STOP: {
        id: "info",
        column: 7,
        label: "",
        width: 40
      },
      ACTION_RUN: {
        id: "action_run",
        column: 8,
        label: "",
        width: 40
      },
      ACTION_RETRY: {
        id: "action_retry",
        column: 9,
        label: "",
        width: 40
      },
      ACTION_MORE: {
        id: "action_more",
        column: 10,
        label: "",
        width: 40
      },
    }
  },

  members: {
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
          const jobInfo = new osparc.jobs.JobInfo(rowData["projectUuid"]);
          const win = osparc.jobs.JobInfo.popUpInWindow(jobInfo);
          win.setCaption(win.getCaption() + " - " + rowData["projectName"]);
          break;
        }
        case "stop":
        case "delete":
        case "logs": {
          const msg = `I wish I could ${action} the job ${rowData["projectUuid"]}`;
          osparc.FlashMessenger.logAs(msg, "WARNING");
          break;
        }
        default:
          console.warn(`Unknown action: ${action}`);
      }
    },
  }
});
