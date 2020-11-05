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

    console.log(nodeId);

    this._setLayout(new qx.ui.layout.VBox());

    const navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    const iframeLayout = this.__iframeLayout = this.__createIframeLayout();
    this._add(iframeLayout, {
      flex: 1
    });

    this.__initLoadingIPage();
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
    __navBar: null,
    __iframeLayout: null,

    __createNavigationBar: function() {
      const navBar = new osparc.viewer.NavigationBar();
      return navBar;
    },

    __createIframeLayout: function() {
      const iframeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      return iframeLayout;
    },

    __initLoadingIPage: function() {
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
      this.__iframeLayout.removeAll();

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
      this.__iframeLayout.add(widget, {
        flex: 1
      });
    }
  }
});
