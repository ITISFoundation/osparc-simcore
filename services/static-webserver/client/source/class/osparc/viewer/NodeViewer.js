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

    this.__initIFrame();
    this.__iFrameChanged();

    this.set({
      studyId,
      nodeId
    });

    this.self().openStudy(studyId)
      .then(() => {
        this.__nodeState();
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

    studyId: {
      check: "String",
      nullable: false
    },

    nodeId: {
      check: "String",
      nullable: false
    },

    serviceUrl: {
      check: "String",
      nullable: true
    },

    dynamicV2: {
      check: "Boolean",
      init: false,
      nullable: true
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
    __initLoadingPage: function() {
      const loadingPage = new osparc.ui.message.Loading().set({
        header: this.tr("Starting viewer")
      });
      this.setLoadingPage(loadingPage);
    },

    __initIFrame: function() {
      this.__initLoadingPage();

      const iframe = new osparc.component.widget.PersistentIframe();
      this.setIFrame(iframe);
    },

    __nodeState: function() {
      const params = {
        url: {
          "studyId": this.getStudyId(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.__onNodeState(data))
        .catch(() => osparc.FlashMessenger.getInstance().logAs(this.tr("There was an error starting the viewer."), "ERROR"));
    },

    __onNodeState: function(data) {
      const serviceState = data["service_state"];
      if (serviceState) {
        this.getLoadingPage().setHeader(serviceState + " viewer");
      }
      switch (serviceState) {
        case "idle": {
          const interval = 1000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "starting":
        case "connecting":
        case "pulling": {
          const interval = 5000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "pending": {
          const interval = 10000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "running": {
          const nodeId = data["service_uuid"];
          if (nodeId !== this.getNodeId()) {
            return;
          }

          const {
            srvUrl,
            isDynamicV2
          } = osparc.utils.Utils.computeServiceUrl(data);
          this.setDynamicV2(isDynamicV2);
          if (srvUrl) {
            this.__waitForServiceReady(srvUrl);
          }
          break;
        }
        case "complete":
          break;
        case "deprecated":
        case "retired":
        case "failed": {
          const msg = this.tr("Service failed: ") + data["service_message"];
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
          return;
        }
        default:
          console.error(serviceState, "service state not supported");
          break;
      }
    },

    __waitForServiceReady: function(srvUrl) {
      // ping for some time until it is really ready
      const pingRequest = new qx.io.request.Xhr(srvUrl);
      pingRequest.addListenerOnce("success", () => {
        this.__serviceReadyIn(srvUrl);
      }, this);
      pingRequest.addListenerOnce("fail", () => {
        const interval = 2000;
        qx.event.Timer.once(() => this.__waitForServiceReady(srvUrl), this, interval);
      });
      pingRequest.send();
    },

    __serviceReadyIn: function(srvUrl) {
      this.setServiceUrl(srvUrl);
      this.__retrieveInputs();
    },

    __retrieveInputs: function() {
      const srvUrl = this.getServiceUrl();
      if (srvUrl) {
        const urlRetrieve = this.isDynamicV2() ? osparc.utils.Utils.computeServiceV2RetrieveUrl(this.getStudyId(), this.getNodeId()) : osparc.utils.Utils.computeServiceRetrieveUrl(srvUrl);
        const updReq = new qx.io.request.Xhr();
        const reqData = {
          "port_keys": []
        };
        updReq.set({
          url: urlRetrieve,
          method: "POST",
          requestData: qx.util.Serializer.toJson(reqData)
        });
        updReq.addListener("success", e => {
          this.getIFrame().setSource(srvUrl);
          this.__iFrameChanged();
        }, this);
        updReq.send();
      }
    },

    __iFrameChanged: function() {
      this._removeAll();

      const loadingPage = this.getLoadingPage();
      const iFrame = this.getIFrame();
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
