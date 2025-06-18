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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const titleLayout = this.__createTitleLayout();
    this._add(titleLayout);

    this.__reloadInterval = setInterval(() => {
      if (this.__subRunsTable) {
        this.__subRunsTable.reloadSubRuns();
      }
    }, 10*1000);
  },

  events: {
    "backToRuns": "qx.event.type.Event",
  },

  members: {
    __titleLabel: null,
    __subRunsTable: null,
    __reloadInterval: null,

    __createTitleLayout: function() {
      const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle",
      }));

      const prevBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Return to Runs"),
        icon: "@FontAwesome5Solid/arrow-left/20",
        backgroundColor: "transparent"
      });
      prevBtn.addListener("execute", () => this.fireEvent("backToRuns"));
      titleLayout.add(prevBtn);

      const titleLabel = this.__titleLabel = new qx.ui.basic.Label().set({
        font: "text-14",
      });
      titleLayout.add(titleLabel, {
        flex: 1
      });

      return titleLayout;
    },

    setProject: function(project) {
      if (this.__subRunsTable) {
        this._remove(this.__subRunsTable);
        this.__subRunsTable = null;
      }

      this.__titleLabel.setValue(project["projectName"])

      const subRunsTable = this.__subRunsTable = new osparc.jobs.SubRunsTable(project["projectUuid"]);
      this._add(subRunsTable, {
        flex: 1
      });
    },

    stopInterval: function() {
      if (this.__reloadInterval) {
        clearInterval(this.__reloadInterval);
      }
    },
  }
})
