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


qx.Class.define("osparc.jobs.RunsBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const reloadButton = this.getChildControl("reload-button");
    reloadButton.addListener("execute", () => this.reloadRuns());
    this.getChildControl("intro-label");
    const jobsFilter = this.getChildControl("jobs-filter");
    const runningCB = this.getChildControl("running-only-cb");
    const runsTable = this.getChildControl("runs-table");

    jobsFilter.getChildControl("textfield").addListener("input", e => {
      const filterText = e.getData();
      runsTable.getTableModel().setFilterString(filterText);
    });

    runningCB.bind("value", runsTable, "runningOnly");
  },

  events: {
    "runSelected": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-toolbar":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "reload-button":
          control = new qx.ui.form.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14");
          this.getChildControl("header-toolbar").add(control);
          break;
        case "intro-label":
          control = new qx.ui.basic.Label(this.tr("Select a Run to check the details"));
          this.getChildControl("header-toolbar").add(control);
          break;
        case "jobs-filter":
          control = new osparc.filter.TextFilter("text", "jobsList").set({
            allowStretchX: true,
            margin: 0
          });
          control.getChildControl("textfield").set({
            placeholder: qx.locale.Manager.tr("Filter by name or ID"),
          });
          control.hide(); // @matusdrobuliak66: remove this when the backend is ready
          this.getChildControl("header-toolbar").add(control, {
            flex: 1
          });
          break;
        case "running-only-cb":
          control = new qx.ui.form.CheckBox().set({
            value: true,
            label: qx.locale.Manager.tr("Active only"),
          });
          this.getChildControl("header-toolbar").add(control);
          break;
        case "runs-table": {
          const projectUuid = null;
          const includeChildren = false;
          const runningOnly = true;
          control = new osparc.jobs.RunsTable(projectUuid, includeChildren, runningOnly);
          control.addListener("runSelected", e => this.fireDataEvent("runSelected", e.getData()));
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    reloadRuns: function() {
      const runsTable = this.getChildControl("runs-table");
      runsTable.reloadRuns();
    },
  }
})
