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
      this._add(new qx.ui.basic.Label(this.tr("Runs History")).set({
        font: "text-14"
      }));

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
      this._add(runsTable);

      this._add(new qx.ui.basic.Label(this.tr("Latest Tasks")).set({
        font: "text-14"
      }));

      const subRunsTable = new osparc.jobs.SubRunsTable(projectData["uuid"]);
      subRunsTable.set({
        maxHeight: 250,
      })
      this._add(subRunsTable);
    },
  }
});
