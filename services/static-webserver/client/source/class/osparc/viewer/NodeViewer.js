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

    this.self().openStudy(studyId)
      .then(studyData => {
        if (studyData["workbench"] && nodeId in studyData["workbench"]) {
          const nodeData = studyData["workbench"][nodeId];
          const key = nodeData["key"];
          const version = nodeData["version"];

          // create study
          const study = new osparc.data.model.Study(studyData);
          this.setStudy(study);

          // create node
          const node = new osparc.data.model.Node(study, key, version, nodeId);
          this.setNode(node);
          node.initIframeHandler();

          const iframeHandler = node.getIframeHandler();
          if (iframeHandler) {
            iframeHandler.startPolling();
            iframeHandler.addListener("iframeChanged", () => this.__buildLayout(), this);
            iframeHandler.getIFrame().addListener("load", () => this.__buildLayout(), this);
            this.__buildLayout();

            this.__attachSocketEventHandlers();
          }
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

  statics: {
    openStudy: function(studyId) {
      const params = {
        url: {
          "studyId": studyId
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "open", params);
    }
  },

  members: {
    __buildLayout: function() {
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
