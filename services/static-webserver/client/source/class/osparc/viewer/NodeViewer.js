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

// Used for "anonymous" or "guest" users

qx.Class.define("osparc.viewer.NodeViewer", {
  extend: qx.ui.core.Widget,

  construct: function(studyId, nodeId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    const params = {
      url: {
        studyId
      },
      data: osparc.utils.Utils.getClientSessionID()
    };
    osparc.data.Resources.fetch("studies", "open", params)
      .then(studyData => {
        // create study
        const study = new osparc.data.model.Study(studyData);
        this.setStudy(study);

        const startPolling = () => {
          const node = study.getWorkbench().getNode(nodeId);
          this.setNode(node);

          node.addListener("retrieveInputs", e => {
            const data = e.getData();
            const portKey = data["portKey"];
            node.retrieveInputs(portKey);
          }, this);

          node.initIframeHandler();

          const iframeHandler = node.getIframeHandler();
          if (iframeHandler) {
            iframeHandler.startPolling();
            iframeHandler.addListener("iframeChanged", () => this.__iFrameChanged(), this);
            iframeHandler.getIFrame().addListener("load", () => this.__iFrameChanged(), this);
            this.__iFrameChanged();

            this.__attachSocketEventHandlers();
          } else {
            console.error(node.getLabel() + " iframe handler not ready");
          }
        }

        if (study.getWorkbench().isDeserialized()) {
          startPolling();
        } else {
          study.getWorkbench().addListener("changeDeserialized", e => {
            if (e.getData()) {
              startPolling();
            }
          });
        }
      })
      .catch(err => console.error(err));
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false
    },

    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false
    }
  },

  members: {
    __iFrameChanged: function() {
      this._removeAll();

      const iframeHandler = this.getNode().getIframeHandler();

      const loadingPage = iframeHandler.getLoadingPage();
      const iFrame = iframeHandler.getIFrame();
      const src = iFrame.getSource();
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      this._add(iFrameView, {
        flex: 1
      });
    },

    __attachSocketEventHandlers: function() {
      this.__listenToNodeUpdated();
      this.__listenToNodeProgress();
    },

    __listenToNodeUpdated: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      if (!socket.slotExists("nodeUpdated")) {
        socket.on("nodeUpdated", data => {
          this.getStudy().nodeUpdated(data);
        }, this);
      }
    },

    __listenToNodeProgress: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      if (!socket.slotExists("nodeProgress")) {
        socket.on("nodeProgress", data => {
          this.getStudy().nodeNodeProgressSequence(data);
        }, this);
      }
    }
  }
});
