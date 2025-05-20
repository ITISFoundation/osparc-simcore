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

    this._setLayout(new qx.ui.layout.VBox(10));

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
    __buildLayout: function(projectData) {
      const runsHistoryTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle",
      })).set({
        paddingLeft: 10,
      });
      const runsHistoryTitle = new qx.ui.basic.Label(this.tr("Runs History")).set({
        font: "text-14"
      });
      runsHistoryTitleLayout.add(runsHistoryTitle);
      const runsHistoryTitleHelper = new osparc.ui.hint.InfoHint(this.tr("In this table, the history of the project runs is shown."))
      runsHistoryTitleLayout.add(runsHistoryTitleHelper);
      this._add(runsHistoryTitleLayout);

      const latestOnly = false;
      const projectUuid = projectData["uuid"];
      const runsTable = new osparc.jobs.RunsTable(latestOnly, projectUuid);
      const columnModel = runsTable.getTableColumnModel();
      // Hide project name column
      columnModel.setColumnVisible(osparc.jobs.RunsTable.COLS.PROJECT_NAME.column, false);
      // Hide cancel column
      columnModel.setColumnVisible(osparc.jobs.RunsTable.COLS.ACTION_CANCEL.column, false);
      runsTable.set({
        maxHeight: 250,
      })
      this._add(runsTable, {
        flex: 1
      });


      const latestTasksTitleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle",
      })).set({
        paddingLeft: 10,
      });
      const latestTasksTitle = new qx.ui.basic.Label(this.tr("Latest Tasks")).set({
        font: "text-14"
      });
      latestTasksTitleLayout.add(latestTasksTitle);
      const latestTasksTitleHelper = new osparc.ui.hint.InfoHint(this.tr("In this table, only the latest tasks or simulations are shown. If available, the logs can be downloaded."))
      latestTasksTitleLayout.add(latestTasksTitleHelper);
      this._add(latestTasksTitleLayout);

      const subRunsTable = new osparc.jobs.SubRunsTable(projectData["uuid"]);
      subRunsTable.set({
        maxHeight: 250,
      })
      this._add(subRunsTable, {
        flex: 1,
      });
    },
  }
});
