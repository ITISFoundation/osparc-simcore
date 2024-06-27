/* ************************************************************************

   explorer - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.viewer.MainPage", {
  extend: qx.ui.core.Widget,

  construct: function(studyId, viewerNodeId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    this._add(osparc.notification.RibbonNotifications.getInstance());

    const navBar = new osparc.viewer.NavigationBar();
    navBar.populateLayout();
    this._add(navBar);

    // Some resources request before building the main stack
    osparc.WindowSizeTracker.getInstance().startTracker();
    osparc.MaintenanceTracker.getInstance().startTracker();

    const store = osparc.store.Store.getInstance();
    const preloadPromises = [];
    preloadPromises.push(store.getAllServices(true));
    Promise.all(preloadPromises)
      .then(() => {
        const nodeViewer = this.__createNodeViewer(studyId, viewerNodeId);
        this._add(nodeViewer, {
          flex: 1
        });
      })
      .catch(err => console.error(err));
  },

  members: {
    __createNodeViewer: function(studyId, viewerNodeId) {
      const nodeViewer = new osparc.viewer.NodeViewer(studyId, viewerNodeId);
      return nodeViewer;
    }
  }
});
