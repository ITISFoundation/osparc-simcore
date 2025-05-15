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

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout(projectData);
  },

  statics: {
    popUpInWindow: function(projectData) {
      const activityOverview = new osparc.jobs.ActivityOverview(projectData);
      const title = qx.locale.Manager.tr("Activity Overview");
      return osparc.ui.window.Window.popUpInWindow(activityOverview, title, osparc.jobs.ActivityCenterWindow.WIDTH, osparc.jobs.ActivityCenterWindow.HEIGHT);
    },
  },

  members: {
    __buildLayout: function(projectData) {
      const latestOnly = false;
      const projectUuid = projectData["uuid"];
      const runsTable = new osparc.jobs.RunsTable(latestOnly, projectUuid);
      this._add(runsTable);

      const subRunsTable = new osparc.jobs.SubRunsTable(projectData["uuid"]);
      this._add(subRunsTable);
    },
  }
});
