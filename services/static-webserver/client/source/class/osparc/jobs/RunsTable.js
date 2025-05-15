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


qx.Class.define("osparc.jobs.RunsTable", {
  extend: qx.ui.table.Table,

  construct: function(filters) {
    this.base(arguments);

    const model = new osparc.jobs.RunsTableModel(filters);
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.PROJECT_UUID.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const iconPathStop = "osparc/icons/circle-xmark-text.svg";
    const fontButtonRendererStop = new osparc.ui.table.cellrenderer.ImageButtonRenderer("cancel", iconPathStop);
    columnModel.setDataCellRenderer(this.self().COLS.ACTION_CANCEL.column, fontButtonRendererStop);

    const iconPathInfo = "osparc/icons/circle-info-text.svg";
    const fontButtonRendererInfo = new osparc.ui.table.cellrenderer.ImageButtonRenderer("info", iconPathInfo);
    columnModel.setDataCellRenderer(this.self().COLS.ACTION_INFO.column, fontButtonRendererInfo);

    this.__attachHandlers();
  },

  events: {
    "runSelected": "qx.event.type.Data",
  },

  statics: {
    COLS: {
      PROJECT_UUID: {
        id: "projectUuid",
        column: 0,
        label: qx.locale.Manager.tr("Project Id"),
        width: 200
      },
      PROJECT_NAME: {
        id: "projectName",
        column: 1,
        label: qx.locale.Manager.tr("Project"),
        width: 150,
        sortable: true
      },
      STATE: {
        id: "state",
        column: 2,
        label: qx.locale.Manager.tr("Status"),
        width: 150
      },
      SUBMIT: {
        id: "submit",
        column: 3,
        label: qx.locale.Manager.tr("Queued"),
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
      ACTION_CANCEL: {
        id: "action_cancel",
        column: 6,
        label: qx.locale.Manager.tr("Cancel"),
        width: 50
      },
      ACTION_INFO: {
        id: "action_info",
        column: 7,
        label: qx.locale.Manager.tr("Info"),
        width: 50
      },
    }
  },

  members: {
    reloadRuns: function() {
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
        } else {
          const rowData = this.getTableModel().getRowData(row);
          this.fireDataEvent("runSelected", rowData);
          this.resetSelection();
        }
      });
    },

    __handleButtonClick: function(action, row) {
      this.resetSelection();
      const rowData = this.getTableModel().getRowData(row);
      switch (action) {
        case "info": {
          const job = osparc.store.Jobs.getInstance().getJob(rowData["projectUuid"]);
          if (!job) {
            return;
          }
          const allInfo = {
            "image": job.getInfo() ? osparc.utils.Utils.deepCloneObject(job.getInfo()) : {},
            "customMetadata": job.getCustomMetadata() ? osparc.utils.Utils.deepCloneObject(job.getCustomMetadata()) : {},
          }
          const runInfo = new osparc.jobs.Info(allInfo);
          const win = osparc.jobs.Info.popUpInWindow(runInfo);
          win.setCaption(rowData["projectName"]);
          break;
        }
        case "cancel": {
          this.__cancelRun(rowData);
          break;
        }
        default:
          console.warn(`Unknown action: ${action}`);
      }
    },

    __cancelRun: function(rowData) {
      const msg = this.tr("Are you sure you want to cancel") + " <b>" + rowData["projectName"] + "</b>?";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Cancel Run"),
        confirmText: this.tr("Cancel"),
        confirmAction: "delete",
      });
      confirmationWin.getChildControl("cancel-button").set({
        label: this.tr("Close"),
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          const params = {
            url: {
              "studyId": rowData["projectUuid"],
            },
          };
          osparc.data.Resources.fetch("runPipeline", "stopPipeline", params)
            .then(() => osparc.FlashMessenger.logAs(this.tr("Stopping pipeline"), "INFO"))
            .catch(err => osparc.FlashMessenger.logError(err));
        }
      }, this);
    },
  }
});
