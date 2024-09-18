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

    osparc.MaintenanceTracker.getInstance().startTracker();

    const nodeViewer = new osparc.viewer.NodeViewer(studyId, viewerNodeId);
    this._add(nodeViewer, {
      flex: 1
    });
  }
});
