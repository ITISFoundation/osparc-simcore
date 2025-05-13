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

  members: {
    __buildLayout: function(projectData) {
      const subRunsTable = new osparc.jobs.SubRunsTable(projectData["uuid"]);
      this._add(subRunsTable);
    },
  }
});
