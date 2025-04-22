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


qx.Class.define("osparc.jobs.SubRunsBrowser", {
  extend: qx.ui.core.Widget,

  construct() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const titleLayout = this.__createTitleLayout();
    this._add(titleLayout);
  },

  events: {
    "backToRuns": "qx.event.type.Event",
  },

  members: {
    __createTitleLayout: function() {
      const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const prevBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Return to Runs and Clusters"),
        icon: "@FontAwesome5Solid/arrow-left/20",
        backgroundColor: "transparent"
      });
      prevBtn.addListener("execute", () => this.fireEvent("backToRuns"));
      titleLayout.add(prevBtn);

      return titleLayout;
    },

    setProjectUuid: function(projectUuid) {
      if (this.__subRunsTable) {
        this._remove(this.__subRunsTable);
        this.__subRunsTable = null;
      }

      const subRunsTable = this.__subRunsTable = new osparc.jobs.SubRunsTable(projectUuid);
      this._add(subRunsTable, {
        flex: 1
      });
    }
  }
})
