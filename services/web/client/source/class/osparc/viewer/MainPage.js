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

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    const navBar = this.__createNavigationBar();
    this._add(navBar);

    const nodeViewer = this.__createNodeViewer();
    this._add(nodeViewer, {
      flex: 1
    });

    const socket = osparc.wrapper.WebSocket.getInstance();
    const slotName = "dataset-viewer";
    socket.removeSlot(slotName);
    socket.on(slotName, viewer => {
      nodeViewer.setNode(viewer);
    });
  },

  members: {
    __iframeLayout: null,

    __createNavigationBar: function() {
      const navBar = new osparc.viewer.NavigationBar();
      return navBar;
    },

    __createNodeViewer: function() {
      const nodeViewer = new osparc.viewer.NodeViewer();
      return nodeViewer;
    }
  }
});
