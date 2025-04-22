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

    const jobsPage = new qx.ui.tabview.Page(this.tr("Jobs")).set({
      layout: new qx.ui.layout.VBox(10)
    });
    const jobsBrowser = new osparc.jobs.RunsBrowser();
    const scroller1 = new qx.ui.container.Scroll();
    scroller1.add(jobsBrowser);
    jobsPage.add(scroller1);
    this.add(jobsPage);

    const clustersPage = new qx.ui.tabview.Page(this.tr("Clusters")).set({
      layout: new qx.ui.layout.VBox(10)
    });
    const clustersBrowser = new osparc.jobs.ClustersBrowser();
    const scroller2 = new qx.ui.container.Scroll();
    scroller2.add(clustersBrowser);
    clustersPage.add(scroller2);
    this.add(clustersPage);
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
});
