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

  construct: function(nodeId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    const navBar = this.__createNavigationBar();
    this._add(navBar);

    const nodeView = this.__createNodeViewer(nodeId);
    this._add(nodeView);
  },

  members: {
    __iframeLayout: null,

    __createNavigationBar: function() {
      const navBar = new osparc.viewer.NavigationBar();
      return navBar;
    },

    __createNodeViewer: function(nodeId) {
      const navBar = new osparc.viewer.NodeViewer(nodeId);
      return navBar;
    }
  }
});
