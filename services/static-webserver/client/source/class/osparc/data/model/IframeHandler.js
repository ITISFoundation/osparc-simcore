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
      const oldStatus = e.getOldData();
      this.__statusInteractiveChanged(newStatus, oldStatus);
    });

    this.__initLoadingPage();
    this.__initLockedPage();
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
      nullable: false,
      event: "changeNode",
      apply: "__applyNode",
    },

    loadingPage: {
      check: "osparc.ui.message.Loading",
      init: null,
      nullable: true
    },

    lockedPage: {
      check: "osparc.ui.message.NodeLockedPage",
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
    "iframeStateChanged": "qx.event.type.Event"
  },

  statics: {
    evalShowToolbar: function(loadingPage, study) {
      if (osparc.product.Utils.isProduct("s4llite")) {
        loadingPage.setShowToolbar(false);
      } else {
        study.getUi().bind("mode", loadingPage, "showToolbar", {
          converter: mode => mode !== "standalone"
        });
      }
    },
  },

  members: {
    __unresponsiveRetries: null,
    __stopRequestingStatus: null,
    __retriesLeft: null,

    checkState: function() {
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

      if (this.getIFrame()) {
        this.getIFrame().resetSource();
      }
    },

    __applyNode: function(node) {
      node.getStatus().getLockState().addListener("changeLocked", () => this.fireEvent("iframeStateChanged"), this);
    },

    __initIFrame: function() {
      const iframe = new osparc.widget.PersistentIframe();
      if (this.getNode().getKey().includes("s4l-ui")) {
        iframe.getIframe().setAppearance("iframe-no-border");
      }
      osparc.utils.Utils.setIdToWidget(iframe.getIframe(), "iframe_"+this.getNode().getNodeId());
      this.self().evalShowToolbar(iframe, this.getStudy());
      iframe.addListener("restart", () => this.restartIFrame(), this);
      iframe.getDiskUsageIndicator().setCurrentNode(this.getNode())
      this.setIFrame(iframe);
    },

    __initLoadingPage: function() {
      const loadingPage = new osparc.ui.message.Loading().set({
        header: this.__getLoadingPageHeader()
      });

      this.self().evalShowToolbar(loadingPage, this.getStudy());

      const node = this.getNode();
      const thumbnail = node.getMetadata()["thumbnail"];
      if (thumbnail) {
        loadingPage.setLogo(thumbnail);
      }
      node.addListener("changeLabel", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);

      const nodeStatus = node.getStatus();
      const sequenceWidget = nodeStatus.getProgressSequence().getWidgetForLoadingPage().set({
        width: 400
      });
      nodeStatus.bind("interactive", sequenceWidget, "visibility", {
        converter: state => ["pending", "pulling", "starting", "connecting"].includes(state) ? "visible" : "excluded"
      });
      loadingPage.addExtraWidget(sequenceWidget);

      this.setLoadingPage(loadingPage);
    },

    __getLoadingPageHeader: function(status) {
      const node = this.getNode();
      if (status === undefined) {
        status = node.getStatus().getInteractive();
      }
      const statusText = status ? (status.charAt(0).toUpperCase() + status.slice(1)) : this.tr("Starting");
      const metadata = node.getMetadata();
      const versionDisplay = osparc.service.Utils.extractVersionDisplay(metadata);
      return statusText + " " + node.getLabel() + " <span style='font-size: 16px;font-weight: normal;'><sub>v" + versionDisplay + "</sub></span>";
    },

    __initLockedPage: function() {
      const lockedPage = new osparc.ui.message.NodeLockedPage();
      this.self().evalShowToolbar(lockedPage, this.getStudy());
      this.bind("node", lockedPage, "node");
      this.setLockedPage(lockedPage);
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
            osparc.FlashMessenger.logAs(node.getLabel() + this.tr(" is retired"), "ERROR");
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
            osparc.FlashMessenger.logAs(this.tr("There was an issue starting") + " " + node.getLabel(), "ERROR");
          }
        });
    },

    onNodeState: function(data) {
      const serviceState = data["service_state"];
      const nodeId = data["service_uuid"];
      const node = this.getNode();
      const status = node.getStatus();
      const loadingPage = this.getLoadingPage();
      loadingPage.clearMessages();
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
            const serviceMessage = data["service_message"];
            loadingPage.setMessages([serviceMessage]);
            // show pending messages only after 10"
            loadingPage.getMessageLabels().forEach(label => label.exclude());
            setTimeout(() => {
              loadingPage.getMessageLabels().forEach(label => label.show());
            }, 10000);
            const serviceName = node.getLabel();
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
          if (
            srvUrl &&
            srvUrl !== node.getServiceUrl() // if it's already connected, do not restart the connection process
          ) {
            this.__statusInteractiveChanged("connecting", node.getStatus().getInteractive());
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
        fetch(srvUrl, {credentials: "include"})
          .then(response => {
            if (osparc.utils.Utils.isDevelopmentPlatform()) {
              console.log("Connecting: fetch's response status", response.status);
            }
            if (response.status < 400) {
              this.__serviceReadyIn(srvUrl);
            } else {
              console.error(`Connecting: ${srvUrl} is not reachable. Status: ${response.status}`);
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

    __statusInteractiveChanged: function(status, oldStatus) {
      if (status === oldStatus) {
        return;
      }

      const node = this.getNode();

      const loadingPage = node.getLoadingPage();
      loadingPage.setHeader(this.__getLoadingPageHeader(status));
      loadingPage.clearMessages();
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
      }

      if (status === "ready") {
        const msg = `Service ${node.getLabel()} ${status}`;
        const msgData = {
          nodeId: node.getNodeId(),
          msg,
          level: "INFO"
        };
        node.fireDataEvent("showInLogger", msgData);

        // will switch to iframe's content
        this.restartIFrame();
        if (!node.isDynamicV2()) {
          node.callRetrieveInputs();
        }
      } else if (["idle", "failed", "stopping"].includes(status) && oldStatus) {
        const msg = `Service ${node.getLabel()} ${status}`;
        const msgData = {
          nodeId: node.getNodeId(),
          msg,
          level: "INFO"
        };
        node.fireDataEvent("showInLogger", msgData);

        // will switch to the loading page
        node.resetServiceUrl();
        if (this.getIFrame()) {
          this.getIFrame().resetSource();
        }
        this.fireEvent("iframeStateChanged");
      }
    },

    restartIFrame: function() {
      const node = this.getNode();
      if (node.getServiceUrl() !== null) {
        // restart button pushed
        if (this.getIFrame() && this.getIFrame().getSource().includes(node.getServiceUrl())) {
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
      if (["running", "ready"].includes(status)) {
        if (this.getIFrame()) {
          this.getIFrame().resetSource();
          this.getIFrame().setSource(node.getServiceUrl());
        }

        // fire event to force switching to iframe's content:
        // it is required in those cases where the native 'load' event isn't triggered (voila)
        this.fireEvent("iframeStateChanged");
      }
    }
  }
});
