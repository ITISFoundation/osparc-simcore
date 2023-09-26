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

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this._add(osparc.notification.RibbonNotifications.getInstance());

    const navBar = this.__createNavigationBar();
    this._add(navBar);

    // Some resources request before building the main stack
    osparc.WindowSizeTracker.getInstance().startTracker();
    osparc.MaintenanceTracker.getInstance().startTracker();

    const nodeViewer = this.__createNodeViewer(studyId, viewerNodeId);
    this._add(nodeViewer, {
      flex: 1
    });
  },

  members: {
    __iframeLayout: null,

    __createNavigationBar: function() {
      const navBar = new osparc.viewer.NavigationBar();
      return navBar;
    },

    __createNodeViewer: function(studyId, viewerNodeId) {
      const nodeViewer = new osparc.viewer.NodeViewer(studyId, viewerNodeId);
      return nodeViewer;
    }
  }
});
