/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.data.model.IframeHandler", {
  extend: qx.core.Object,
  include: qx.locale.MTranslation,

  construct: function(study, node) {
    this.setStudy(study);
    this.setNode(node);

    node.getStatus().addListener("changeInteractive", e => {
      const newStatus = e.getData();
      const oldStatus = e.getData();
      this.__statusInteractiveChanged(newStatus, oldStatus);
    });

    this.__initLoadingPage();
    this.__initIFrame();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false,
      event: "changeStudy"
    },

    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false
    },

    loadingPage: {
      check: "osparc.ui.message.Loading",
      init: null,
      nullable: true
    },

    iFrame: {
      check: "osparc.widget.PersistentIframe",
      init: null,
      nullable: true
    }
  },

  events: {
    "iframeChanged": "qx.event.type.Event"
  },

  members: {
    __unresponsiveRetries: null,
    __stopRequestingStatus: null,
    __retriesLeft: null,

    startPolling: function() {
      this.getNode().getStatus().getProgressSequence()
        .resetSequence();

      this.__unresponsiveRetries = 5;
      this.__nodeState();
    },

    stopIframe: function() {
      this.getNode().getStatus().getProgressSequence()
        .resetSequence();

      this.__unresponsiveRetries = 5;
      this.__nodeState();

      this.getIFrame().resetSource();
    },

    __initIFrame: function() {
      const iframe = new osparc.widget.PersistentIframe();
      osparc.utils.Utils.setIdToWidget(iframe.getIframe(), "iframe_"+this.getNode().getNodeId());
      if (osparc.product.Utils.isProduct("s4llite")) {
        iframe.setShowToolbar(false);
      }
      iframe.addListener("restart", () => this.__restartIFrame(), this);
      iframe.getDiskUsageIndicator().setCurrentNode(this.getNode())
      this.setIFrame(iframe);
    },

    __initLoadingPage: function() {
      const showZoomMaximizeButton = !osparc.product.Utils.isProduct("s4llite");
      const loadingPage = new osparc.ui.message.Loading(showZoomMaximizeButton);
      loadingPage.set({
        header: this.__getLoadingPageHeader()
      });

      const node = this.getNode();
      const thumbnail = node.getMetaData()["thumbnail"];
      if (thumbnail) {
        loadingPage.setLogo(thumbnail);
      }
      node.addListener("changeLabel", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);

      const nodeStatus = node.getStatus();
      const sequenceWidget = nodeStatus.getProgressSequence().getWidgetForLoadingPage();
      nodeStatus.bind("interactive", sequenceWidget, "visibility", {
        converter: state => ["starting", "pulling", "pending", "connecting"].includes(state) ? "visible" : "excluded"
      });
      loadingPage.addExtraWidget(sequenceWidget);

      nodeStatus.addListener("changeInteractive", () => {
        loadingPage.setHeader(this.__getLoadingPageHeader());
        const status = nodeStatus.getInteractive();
        if (["idle", "failed"].includes(status)) {
          const startButton = new qx.ui.form.Button().set({
            label: this.tr("Start"),
            icon: "@FontAwesome5Solid/play/18",
            font: "text-18",
            allowGrowX: false,
            height: 32
          });
          startButton.addListener("execute", () => node.requestStartNode());
          loadingPage.addWidgetToMessages(startButton);
        } else {
          loadingPage.setMessages([]);
        }
      }, this);
      this.setLoadingPage(loadingPage);
    },

    __getLoadingPageHeader: function() {
      const node = this.getNode();
      let statusText = this.tr("Starting");
      const status = node.getStatus().getInteractive();
      if (status) {
        statusText = status.charAt(0).toUpperCase() + status.slice(1);
      }
      const metadata = node.getMetaData();
      const versionDisplay = osparc.service.Utils.extractVersionDisplay(metadata);
      return statusText + " " + node.getLabel() + " <span style='font-size: 16px;font-weight: normal;'><sub>v" + versionDisplay + "</sub></span>";
    },

    __nodeState: function() {
      // Check if study is still there
      if (this.getStudy() === null || this.__stopRequestingStatus === true) {
        return;
      }
      // Check if node is still there
      if (this.getStudy().getWorkbench().getNode(this.getNode().getNodeId()) === null) {
        return;
      }

      const node = this.getNode();
      const params = {
        url: {
          studyId: this.getStudy().getUuid(),
          nodeId: node.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.onNodeState(data))
        .catch(err => {
          let errorMsg = `Error retrieving ${node.getLabel()} status: ${err}`;
          if ("status" in err && err.status === 406) {
            errorMsg = node.getKey() + ":" + node.getVersion() + "is retired";
            node.getStatus().setInteractive("retired");
            osparc.FlashMessenger.getInstance().logAs(node.getLabel() + this.tr(" is retired"), "ERROR");
          }
          const errorMsgData = {
            nodeId: node.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          node.fireDataEvent("showInLogger", errorMsgData);
          if ("status" in err && err.status === 406) {
            return;
          }
          if (this.__unresponsiveRetries > 0) {
            const retryMsg = `Retrying (${this.__unresponsiveRetries})`;
            const retryMsgData = {
              nodeId: node.getNodeId(),
              msg: retryMsg,
              level: "ERROR"
            };
            node.fireDataEvent("showInLogger", retryMsgData);
            this.__unresponsiveRetries--;
          } else {
            node.getStatus().setInteractive("failed");
            osparc.FlashMessenger.getInstance().logAs(this.tr("There was an error starting") + " " + node.getLabel(), "ERROR");
          }
        });
    },

    onNodeState: function(data) {
      const serviceState = data["service_state"];
      const nodeId = data["service_uuid"];
      const node = this.getNode();
      const status = node.getStatus();
      switch (serviceState) {
        case "idle": {
          status.setInteractive(serviceState);
          if (this.__unresponsiveRetries>0) {
            // a bit of a hack. We will get rid of it when the backend pushes the states
            this.__unresponsiveRetries--;
          }
          break;
        }
        case "pending": {
          if (data["service_message"]) {
            const serviceName = node.getLabel();
            const serviceMessage = data["service_message"];
            const msg = `The service "${serviceName}" is waiting for available ` +
              `resources. Please inform support and provide the following message ` +
              `in case this does not resolve in a few minutes: "${nodeId}" ` +
              `reported "${serviceMessage}"`;
            const msgData = {
              nodeId: node.getNodeId(),
              msg: msg,
              level: "INFO"
            };
            node.fireDataEvent("showInLogger", msgData);
          }
          status.setInteractive(serviceState);
          break;
        }
        case "stopping":
        case "unknown":
        case "starting":
        case "pulling": {
          status.setInteractive(serviceState);
          break;
        }
        case "running": {
          if (nodeId !== node.getNodeId()) {
            break;
          }
          const {
            srvUrl,
            isDynamicV2
          } = osparc.utils.Utils.computeServiceUrl(data);
          node.setDynamicV2(isDynamicV2);
          if (srvUrl) {
            status.setInteractive("connecting");
            this.__retriesLeft = 40;
            this.__waitForServiceReady(srvUrl);
          }
          break;
        }
        case "complete":
          break;
        case "failed": {
          status.setInteractive(serviceState);
          const msg = "Service failed: " + data["service_message"];
          const errorMsgData = {
            nodeId: node.getNodeId(),
            msg,
            level: "ERROR"
          };
          node.fireDataEvent("showInLogger", errorMsgData);
          return;
        }
        default:
          console.error(serviceState, "service state not supported");
          break;
      }
    },

    __waitForServiceReady: function(srvUrl) {
      if (this.__retriesLeft === 0) {
        return;
      }

      const retry = () => {
        this.__retriesLeft--;

        // Check if node is still there
        if (this.getStudy().getWorkbench().getNode(this.getNode().getNodeId()) === null) {
          return;
        }
        const interval = 5000;
        qx.event.Timer.once(() => this.__waitForServiceReady(srvUrl), this, interval);
      };

      // ping for some time until it is really reachable
      try {
        if (osparc.utils.Utils.isDevelopmentPlatform()) {
          console.log("Connecting: about to fetch", srvUrl);
        }
        fetch(srvUrl)
          .then(response => {
            if (osparc.utils.Utils.isDevelopmentPlatform()) {
              console.log("Connecting: fetch's response status", response.status);
            }
            if (response.status < 400) {
              this.__serviceReadyIn(srvUrl);
            } else {
              console.log(`Connecting: ${srvUrl} is not reachable. Status: ${response.status}`);
              retry();
            }
          })
          .catch(err => {
            console.error("Connecting: Error", err);
            retry();
          });
      } catch (error) {
        console.error(`Connecting: Error while checking ${srvUrl}:`, error);
        retry();
      }
    },

    __serviceReadyIn: function(srvUrl) {
      const node = this.getNode();
      node.setServiceUrl(srvUrl);
      node.getStatus().setInteractive("ready");
    },

    __statusInteractiveChanged: function(newStatus, oldStatus) {
      const node = this.getNode();

      if (newStatus === "ready") {
        const srvUrl = node.getServiceUrl();
        const msg = "Service ready on " + srvUrl;
        const msgData = {
          nodeId: node.getNodeId(),
          msg,
          level: "INFO"
        };
        node.fireDataEvent("showInLogger", msgData);
        // will switch to iframe's content
        this.__restartIFrame();
        if (!node.isDynamicV2()) {
          node.callRetrieveInputs();
        }
      }
      if (oldStatus === "ready") {
        // will switch to loading page
        this.__restartIFrame();
      }
    },

    __restartIFrame: function() {
      const node = this.getNode();
      if (node.getServiceUrl() !== null) {
        // restart button pushed
        if (this.getIFrame().getSource().includes(node.getServiceUrl())) {
          this.__loadIframe();
        }

        const loadingPage = this.getLoadingPage();
        const bounds = loadingPage.getBounds();
        const domEle = loadingPage.getContentElement().getDomElement();
        const boundsCR = domEle ? domEle.getBoundingClientRect() : null;
        if (bounds !== null && boundsCR && boundsCR.width > 0) {
          this.__loadIframe();
        } else {
          // lazy loading
          loadingPage.addListenerOnce("appear", () => this.__loadIframe(), this);
        }
      }
    },

    __loadIframe: function() {
      const node = this.getNode();
      const status = node.getStatus().getInteractive();
      // it might have been stopped
      if (status === "ready") {
        this.getIFrame().resetSource();
        this.getIFrame().setSource(node.getServiceUrl());

        // fire event to force switching to iframe's content:
        // it is required in those cases where the native 'load' event isn't triggered (voila)
        this.fireEvent("iframeChanged");
      }
    }
  }
});
