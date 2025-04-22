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


qx.Class.define("osparc.jobs.RunsAndClusters", {
  extend: qx.ui.tabview.TabView,

  construct() {
    this.base(arguments);

    this.set({
      contentPadding: 5,
      barPosition: "top",
    });

    const runsBrowser = this.getChildControl("runs-browser");
    runsBrowser.addListener("runSelected", e => this.fireDataEvent("runSelected", e.getData()));

    this.getChildControl("clusters-browser");
  },

  events: {
    "runSelected": "qx.event.type.Data",
  },

  statics: {
    popUpInWindow: function(jobsAndClusters) {
      if (!jobsAndClusters) {
        jobsAndClusters = new osparc.jobs.RunsAndClusters();
      }
      const title = qx.locale.Manager.tr("Runs and Clusters");
      const win = osparc.ui.window.Window.popUpInWindow(jobsAndClusters, title, 1100, 500);
      win.open();
      return win;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "jobs-page":
          control = new qx.ui.tabview.Page(this.tr("Runs")).set({
            layout: new qx.ui.layout.VBox(10)
          });
          this.add(control);
          break;
        case "runs-browser": {
          control = new osparc.jobs.RunsBrowser();
          const scroller = new qx.ui.container.Scroll();
          scroller.add(control);
          this.getChildControl("jobs-page").add(scroller);
          break;
        }
        case "clusters-page":
          control = new qx.ui.tabview.Page(this.tr("Clusters")).set({
            layout: new qx.ui.layout.VBox(10)
          });
          this.add(control);
          break;
        case "clusters-browser": {
          control = new osparc.jobs.ClustersBrowser();
          const scroller = new qx.ui.container.Scroll();
          scroller.add(control);
          this.getChildControl("clusters-page").add(scroller);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    reloadRuns: function() {
      const runsBrowser = this.getChildControl("runs-browser");
      runsBrowser.reloadRuns();
    },
  }
});
