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

          // create node
          const node = new osparc.data.model.Node(study, key, version, nodeId);
          node.initIframeHandler();
          this.__iframeHandler = node.getIframeHandler();
          this.__iframeHandler.startPolling();

          this.__iframeHandler.addListener("iframeChanged", () => this.__buildLayout(), this);
          this.__iframeHandler.getIFrame().addListener("load", () => this.__buildLayout(), this);
          this.__buildLayout();
        }
      })
      .catch(err => console.error(err));
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
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      /*
      this.getLayoutParent().set({
        zIndex: iFrame.getZIndex()-1
      });
      */
      this._add(iFrameView, {
        flex: 1
      });
    }
  }
});
