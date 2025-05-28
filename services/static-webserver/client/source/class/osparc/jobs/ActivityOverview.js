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

qx.Class.define("osparc.jobs.ActivityOverview", {
  extend: qx.ui.core.Widget,

  construct: function(projectData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout(projectData);
  },

  statics: {
    popUpInWindow: function(projectData) {
      const activityOverview = new osparc.jobs.ActivityOverview(projectData);
      const title = qx.locale.Manager.tr("Activity Overview") + " - " + projectData["name"];
      const win = osparc.ui.window.Window.popUpInWindow(activityOverview, title, osparc.jobs.ActivityCenterWindow.WIDTH, osparc.jobs.ActivityCenterWindow.HEIGHT);
      win.set({
        maxHeight: 700,
      });
      return win;
    },
  },

  members: {
    __runsTable: null,
    __subRunsTable: null,

    __buildLayout: function(projectData) {
      const stack = new qx.ui.container.Stack();
      this._add(stack, {
        flex: 1
      });

      const runsHistoryLayout = this.__createRunsHistoryView(projectData);
      stack.add(runsHistoryLayout);

      const tasksLayout = this.__createTasksView();
      stack.add(tasksLayout);

      this.__runsTable.addListener("runSelected", e => {
        const data = e.getData();
        const project = data["rowData"];
        const projectUuid = project["projectUuid"];
        // Hacky-hacky
        for (let i=0; i<this.__runsTable.getTableModel().getRowCount(); i++) {
          const rowData = this.__runsTable.getTableModel().getRowData(i);
          if (rowData["projectUuid"] === projectUuid && data["rowIdx"] > i) {
            const msg = this.tr("Only the latest run's tasks are available");
            osparc.FlashMessenger.logAs(msg, "WARNING");
            return;
          }
        }

        if (this.__subRunsTable) {
          tasksLayout.remove(this.__subRunsTable);
          this.__subRunsTable = null;
        }
        const subRunsTable = this.__subRunsTable = new osparc.jobs.SubRunsTable(project["projectUuid"]);
        tasksLayout.add(subRunsTable, {
          flex: 1
        });
        stack.setSelection([tasksLayout]);

        tasksLayout.addListener("backToRuns", () => {
          stack.setSelection([runsHistoryLayout]);
        });
      }, this);
    },

    __createRunsHistoryView: function(projectData) {
      const runsHistoryLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const runsHistoryTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle",
      })).set({
        paddingLeft: 10,
      });
      const runsHistoryTitle = new qx.ui.basic.Label(this.tr("Runs History")).set({
        font: "text-14"
      });
      runsHistoryTitleLayout.add(runsHistoryTitle);
      const runsHistoryTitleHelper = new osparc.ui.hint.InfoHint(this.tr("In this table, the history of the project runs is shown. Select a run to see its tasks."))
      runsHistoryTitleLayout.add(runsHistoryTitleHelper);
      runsHistoryLayout.add(runsHistoryTitleLayout);

      const projectUuid = projectData["uuid"];
      const includeChildren = true;
      const runningOnly = false;
      const runsTable = this.__runsTable = new osparc.jobs.RunsTable(projectUuid, includeChildren, runningOnly);
      const columnModel = runsTable.getTableColumnModel();
      // Hide project name column
      columnModel.setColumnVisible(osparc.jobs.RunsTable.COLS.PROJECT_NAME.column, false);
      // Hide cancel column
      columnModel.setColumnVisible(osparc.jobs.RunsTable.COLS.ACTION_CANCEL.column, false);
      runsHistoryLayout.add(runsTable, {
        flex: 1
      });

      return runsHistoryLayout;
    },

    __createTasksView: function() {
      const tasksLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const latestTasksTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle",
      })).set({
        paddingLeft: 10,
      });

      const prevBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Return to Runs"),
        icon: "@FontAwesome5Solid/arrow-left/20",
        backgroundColor: "transparent"
      });
      prevBtn.addListener("execute", () => tasksLayout.fireEvent("backToRuns"));
      latestTasksTitleLayout.add(prevBtn);

      const latestTasksTitle = new qx.ui.basic.Label(this.tr("Tasks")).set({
        font: "text-14"
      });
      latestTasksTitleLayout.add(latestTasksTitle);
      const latestTasksTitleHelper = new osparc.ui.hint.InfoHint(this.tr("In this table, the tasks or simulations of the selected run are shown. If available, the logs can be downloaded."))
      latestTasksTitleLayout.add(latestTasksTitleHelper);
      tasksLayout.add(latestTasksTitleLayout);

      return tasksLayout;
    },
  }
});
