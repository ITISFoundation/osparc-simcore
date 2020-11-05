/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.viewer.NodeViewer", {
  extend: qx.ui.core.Widget,

  construct: function(nodeId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    console.log(nodeId);

    this.__initLoadingPage();
    this.__initIFrame();

    this.__iFrameChanged();

    setTimeout(() => {
      this.getIFrame().setSource("http://localhost:9000/#/services");
      this.__iFrameChanged();
    }, 10000);
  },

  properties: {
    loadingPage: {
      check: "osparc.ui.message.Loading",
      init: null,
      nullable: true
    },

    iFrame: {
      check: "osparc.component.widget.PersistentIframe",
      init: null,
      nullable: true
    }
  },

  members: {
    __initLoadingPage: function() {
      const loadingPage = new osparc.ui.message.Loading("Starting viewer");
      this.setLoadingPage(loadingPage);
    },

    __initIFrame: function() {
      const iframe = new osparc.component.widget.PersistentIframe().set({
        showActionButton: false,
        showRestartButton: false
      });
      this.setIFrame(iframe);
    },

    __iFrameChanged: function() {
      this._removeAll();

      const loadingPage = this.getLoadingPage();
      const iFrame = this.getIFrame();
      const src = iFrame.getSource();
      let widget;
      if (src === null || src === "about:blank") {
        widget = loadingPage;
      } else {
        this.set({
          zIndex: 9
        });
        widget = iFrame;
      }
      this._add(widget, {
        flex: 1
      });
    }
  }
});
