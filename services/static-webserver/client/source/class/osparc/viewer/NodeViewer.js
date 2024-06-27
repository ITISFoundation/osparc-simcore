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
        const study = new osparc.data.model.Study(studyData);
        this.setStudy(study);

        // create node
        if (studyData["workbench"] && nodeId in studyData["workbench"]) {
          const nodeData = studyData["workbench"][nodeId];
          const key = nodeData["key"];
          const version = nodeData["version"];
          const node = new osparc.data.model.Node(study, key, version, nodeId);
          this.setNode(node);

          this.__iframeHandler = new osparc.data.model.IframeHandler(this.getStudy(), this.getNode());
          this.__iframeHandler.startPolling();

          this.__buildLayout();
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
    __iframeHandler: null,

    __buildLayout: function() {
      this._removeAll();

      const loadingPage = this.__iframeHandler.getLoadingPage();
      const iFrame = this.__iframeHandler.getIFrame();
      const src = iFrame.getSource();
      let iFrameView;
      if (src === null || src === "about:blank") {
        iFrameView = loadingPage;
      } else {
        this.getLayoutParent().set({
          zIndex: iFrame.getZIndex()-1
        });
        iFrameView = iFrame;
      }
      this._add(iFrameView, {
        flex: 1
      });
    }
  }
});
