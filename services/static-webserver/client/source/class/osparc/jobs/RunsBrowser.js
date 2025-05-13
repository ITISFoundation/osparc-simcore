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

    const jobsFilter = this.getChildControl("jobs-filter");
    const jobsTable = this.getChildControl("runs-table");

    jobsFilter.getChildControl("textfield").addListener("input", e => {
      const filterText = e.getData();
      jobsTable.getTableModel().setFilters({
        text: filterText,
      });
    });

    this.__reloadInterval = setInterval(() => this.getChildControl("runs-table").reloadRuns(), 10*1000);
  },

  events: {
    "runSelected": "qx.event.type.Data",
  },

  members: {
    __reloadInterval: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-filter":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "jobs-filter":
          control = new osparc.filter.TextFilter("text", "jobsList").set({
            allowStretchX: true,
            margin: 0
          });
          this.getChildControl("header-filter").add(control, {
            flex: 1
          });
          break;
        case "runs-table":
          control = new osparc.jobs.RunsTable();
          control.addListener("runSelected", e => this.fireDataEvent("runSelected", e.getData()));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    reloadRuns: function() {
      const runsTable = this.getChildControl("runs-table");
      runsTable.reloadRuns();
    },

    stopInterval: function() {
      if (this.__reloadInterval) {
        clearInterval(this.__reloadInterval);
      }
    },
  }
})
