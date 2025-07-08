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

  construct: function(projectId = null, runningOnly = true) {
    this.base(arguments);

    this.set({
      projectId,
      runningOnly,
    });

    const model = new osparc.jobs.RunsTableModel(projectId);
    this.bind("projectId", model, "projectId");
    this.bind("runningOnly", model, "runningOnly");
    this.setTableModel(model);

    this.set({
      statusBarVisible: false,
      headerCellHeight: 26,
      rowHeight: 26,
    });

    const columnModel = this.getTableColumnModel();
    columnModel.setColumnVisible(this.self().COLS.COLLECTION_RUN_ID.column, false);
    columnModel.setColumnVisible(this.self().COLS.PROJECT_IDS.column, false);

    Object.values(this.self().COLS).forEach(col => columnModel.setColumnWidth(col.column, col.width));

    const iconPathStop = "osparc/icons/circle-xmark-text.svg";
    const fontButtonRendererStop = new osparc.ui.table.cellrenderer.ImageButtonRenderer("cancel", iconPathStop);
    columnModel.setDataCellRenderer(this.self().COLS.ACTION_CANCEL.column, fontButtonRendererStop);

    const iconPathInfo = "osparc/icons/circle-info-text.svg";
    const fontButtonRendererInfo = new osparc.ui.table.cellrenderer.ImageButtonRenderer("info", iconPathInfo);
    columnModel.setDataCellRenderer(this.self().COLS.ACTION_INFO.column, fontButtonRendererInfo);

    this.__attachHandlers();
  },

  properties: {
    projectId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeProjectId",
    },

    runningOnly: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeRunningOnly",
    },
  },

  events: {
    "runSelected": "qx.event.type.Data",
  },

  statics: {
    COLS: {
      COLLECTION_RUN_ID: {
        id: "collectionRunId",
        column: 0,
        label: qx.locale.Manager.tr("Collection Run Id"),
        width: 200
      },
      PROJECT_IDS: {
        id: "projectIds",
        column: 1,
        label: qx.locale.Manager.tr("Project Ids"),
        width: 200
      },
      NAME: {
        id: "name",
        column: 2,
        label: qx.locale.Manager.tr("Name"),
        width: 150,
      },
      STATE: {
        id: "state",
        column: 3,
        label: qx.locale.Manager.tr("Status"),
        width: 150,
      },
      SUBMIT: {
        id: "submit",
        column: 4,
        label: qx.locale.Manager.tr("Queued"),
        width: 130,
        sortableMap: "submitted_at",
      },
      START: {
        id: "start",
        column: 5,
        label: qx.locale.Manager.tr("Started"),
        width: 130,
        sortableMap: "started_at",
      },
      END: {
        id: "end",
        column: 6,
        label: qx.locale.Manager.tr("Ended"),
        width: 130,
        sortableMap: "ended_at",
      },
      ACTION_CANCEL: {
        id: "action_cancel",
        column: 7,
        label: qx.locale.Manager.tr("Cancel"),
        width: 50
      },
      ACTION_INFO: {
        id: "action_info",
        column: 8,
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
        const rowIdx = e.getRow();
        const target = e.getOriginalTarget();
        if (target.closest(".qx-material-button") && (target.tagName === "IMG" || target.tagName === "DIV")) {
          const action = target.closest(".qx-material-button").getAttribute("data-action");
          if (action) {
            this.__handleButtonClick(action, rowIdx);
          }
        } else {
          const rowData = this.getTableModel().getRowData(rowIdx);
          this.fireDataEvent("runSelected", {
            rowData,
            rowIdx,
          });
          this.resetSelection();
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
          const info = job.getInfo() ? osparc.utils.Utils.deepCloneObject(job.getInfo()) : {}
          const runInfo = new osparc.jobs.Info(info);
          const win = osparc.jobs.Info.popUpInWindow(runInfo);
          win.setCaption(rowData["name"]);
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
      const msg = this.tr("Are you sure you want to cancel") + " <b>" + rowData["name"] + "</b>?";
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
              "studyId": rowData["projectId"],
            },
          };
          // confirm with @matusdrobuliak66 if this works
          osparc.data.Resources.fetch("runPipeline", "stopPipeline", params)
            .then(() => osparc.FlashMessenger.logAs(this.tr("Stopping pipeline"), "INFO"))
            .catch(err => osparc.FlashMessenger.logError(err));
        }
      }, this);
    },
  }
});
