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
    }
  },

  statics: {
    openStudy: function(studyId) {
      const params = {
        url: {
          projectId: studyId
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "open", params);
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

    __nodeState: function() {
      const params = {
        url: {
          projectId: this.getStudyId(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.__onNodeState(data))
        .catch(() => osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error starting the viewer."), "ERROR"));
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
          const servicePath = data["service_basepath"];
          const entryPointD = data["entry_point"];
          const serviceUuid = data["service_uuid"];
          if (serviceUuid !== this.getNodeId()) {
            return;
          }
          if (servicePath) {
            const entryPoint = entryPointD ? ("/" + entryPointD) : "/";
            const srvUrl = servicePath + entryPoint;
            this.__waitForServiceReady(srvUrl);
          }
          break;
        }
        case "complete":
          break;
        case "failed": {
          const msg = this.tr("Service failed: ") + data["service_message"];
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
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
        // retrieveInputs
        let urlUpdate = srvUrl + "/retrieve";
        urlUpdate = urlUpdate.replace("//retrieve", "/retrieve");
        const updReq = new qx.io.request.Xhr();
        const reqData = {
          "port_keys": []
        };
        updReq.set({
          url: urlUpdate,
          method: "POST",
          requestData: qx.util.Serializer.toJson(reqData)
        });
        updReq.addListener("success", e => {
          this.getIFrame().setSource(srvUrl);
          this.__iFrameChanged();
        }, this);
        updReq.send();
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
    }
  }
});
