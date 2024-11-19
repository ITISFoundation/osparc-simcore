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

        if (study.getWorkbench().isDeserialized()) {
          this.__initStudy(study, nodeId);
        } else {
          study.getWorkbench().addListener("changeDeserialized", e => {
            if (e.getData()) {
              this.__initStudy(study, nodeId);
            }
          }, this);
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
    __initStudy: function(study, nodeId) {
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
        iframeHandler.checkState();
        iframeHandler.addListener("iframeChanged", () => this.__iFrameChanged(), this);
        iframeHandler.getIFrame().addListener("load", () => this.__iFrameChanged(), this);
        this.__iFrameChanged();

        this.__attachSocketEventHandlers();
      } else {
        console.error(node.getLabel() + " iframe handler not ready");
      }
    },

    __iFrameChanged: function() {
      this._removeAll();

      if (this.getNode() && this.getNode().getIframeHandler()) {
        const iframeHandler = this.getNode().getIframeHandler();
        const loadingPage = iframeHandler.getLoadingPage();
        const iFrame = iframeHandler.getIFrame();
        const src = iFrame.getSource();
        const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
        this._add(iFrameView, {
          flex: 1
        });
      }
    },

    __attachSocketEventHandlers: function() {
      this.__listenToNodeUpdated();
      this.__listenToNodeProgress();
      this.__listenToServiceStatus();
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
    },

    __listenToServiceStatus: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      // callback for events
      if (!socket.slotExists("serviceStatus")) {
        socket.on("serviceStatus", data => {
          const nodeId = data["service_uuid"];
          const workbench = this.getStudy().getWorkbench();
          const node = workbench.getNode(nodeId);
          if (node) {
            if (node.getIframeHandler()) {
              node.getIframeHandler().onNodeState(data);
            }
          } else if (osparc.data.Permissions.getInstance().isTester()) {
            console.log("Ignored ws 'progress' msg", data);
          }
        }, this);
      }
    }
  }
});
