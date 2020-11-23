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

  construct: function(studyId, nodeId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    this.__initLoadingPage();
    this.__initIFrame();

    this.__iFrameChanged();

    this.__openStudy(studyId)
      .then(() => {
        const src = window.location.href + "x/" + nodeId;
        this.__waitForServiceReady(src);
      })
      .catch(err => {
        console.error(err);
      });
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
    },

    node: {
      check: "Object",
      apply: "__applyNode",
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

    __openStudy: function(studyId) {
      const params = {
        url: {
          projectId: studyId
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "open", params);
    },

    __waitForServiceReady: function(srvUrl) {
      // ping for some time until it is really ready
      const pingRequest = new qx.io.request.Xhr(srvUrl);
      pingRequest.addListenerOnce("success", () => {
        this.getIFrame().setSource(srvUrl);
        this.__iFrameChanged();
      }, this);
      pingRequest.addListenerOnce("fail", () => {
        const interval = 2000;
        qx.event.Timer.once(() => this.__waitForServiceReady(srvUrl), this, interval);
      });
      pingRequest.send();
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
        this.getLayoutParent().set({
          zIndex: iFrame.getZIndex()-1
        });
        widget = iFrame;
      }
      this._add(widget, {
        flex: 1
      });
    },

    __applyNode: function(viewer) {
      console.log(viewer);
    }
  }
});
