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

/**
 * Mixin included in Node and NodeViewer (node viewer for guest users)
 */

qx.Mixin.define("osparc.data.model.mixin.NodeStatePoller", {

  events: {
    "iframeChanged": "qx.event.typeEvent"
  },

  members: {
    __unresponsiveRetries: null,
    __stopRequestingStatus: null,
    __retriesLeft: null,

    startDynamicService: function() {
      if (this.isDynamic()) {
        this.getStatus().getProgressSequence().resetSequence();

        const metaData = this.getMetaData();
        const msg = "Starting " + metaData.key + ":" + metaData.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg,
          level: "INFO"
        };
        this.fireDataEvent("showInLogger", msgData);

        this.__unresponsiveRetries = 5;
        this.__nodeState();
      }
    },

    __initIFrame: function() {
      this.__initLoadingPage();

      const iframe = new osparc.widget.PersistentIframe();
      osparc.utils.Utils.setIdToWidget(iframe.getIframe(), "iframe_"+this.getNodeId());
      if (osparc.product.Utils.isProduct("s4llite")) {
        iframe.setShowToolbar(false);
      }
      iframe.addListener("restart", () => this.__restartIFrame(), this);
      iframe.getDiskUsageIndicator().setCurrentNode(this)
      this.setIFrame(iframe);
    },

    __initLoadingPage: function() {
      const showZoomMaximizeButton = !osparc.product.Utils.isProduct("s4llite");
      const loadingPage = new osparc.ui.message.Loading(showZoomMaximizeButton);
      loadingPage.set({
        header: this.__getLoadingPageHeader()
      });

      const thumbnail = this.getMetaData()["thumbnail"];
      if (thumbnail) {
        loadingPage.setLogo(thumbnail);
      }
      this.addListener("changeLabel", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);

      const nodeStatus = this.getStatus();
      const sequenceWidget = nodeStatus.getProgressSequence().getWidgetForLoadingPage();
      nodeStatus.bind("interactive", sequenceWidget, "visibility", {
        converter: state => ["starting", "pulling", "pending", "connecting"].includes(state) ? "visible" : "excluded"
      });
      loadingPage.addExtraWidget(sequenceWidget);

      this.getStatus().addListener("changeInteractive", () => {
        loadingPage.setHeader(this.__getLoadingPageHeader());
        const status = this.getStatus().getInteractive();
        if (["idle", "failed"].includes(status)) {
          const startButton = new qx.ui.form.Button().set({
            label: this.tr("Start"),
            icon: "@FontAwesome5Solid/play/18",
            font: "text-18",
            allowGrowX: false,
            height: 32
          });
          startButton.addListener("execute", () => this.requestStartNode());
          loadingPage.addWidgetToMessages(startButton);
        } else {
          loadingPage.setMessages([]);
        }
      }, this);
      this.setLoadingPage(loadingPage);
    },

    __getLoadingPageHeader: function() {
      let statusText = this.tr("Starting");
      const status = this.getStatus().getInteractive();
      if (status) {
        statusText = status.charAt(0).toUpperCase() + status.slice(1);
      }
      return statusText + " " + this.getLabel() + " <span style='font-size: 16px;font-weight: normal;'><sub>v" + this.getVersion() + "</sub></span>";
    },

    __nodeState: function(starting=true) {
      // Check if study is still there
      if (this.getStudy() === null || this.__stopRequestingStatus === true) {
        return;
      }
      // Check if node is still there
      if (this.getWorkbench().getNode(this.getNodeId()) === null) {
        return;
      }

      const params = {
        url: {
          studyId: this.getStudy().getUuid(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.__onNodeState(data, starting))
        .catch(err => {
          let errorMsg = `Error retrieving ${this.getLabel()} status: ${err}`;
          if ("status" in err && err.status === 406) {
            errorMsg = this.getKey() + ":" + this.getVersion() + "is retired";
            this.getStatus().setInteractive("retired");
            osparc.FlashMessenger.getInstance().logAs(this.getLabel() + this.tr(" is retired"), "ERROR");
          }
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          if ("status" in err && err.status === 406) {
            return;
          }
          if (this.__unresponsiveRetries > 0) {
            const retryMsg = `Retrying (${this.__unresponsiveRetries})`;
            const retryMsgData = {
              nodeId: this.getNodeId(),
              msg: retryMsg,
              level: "ERROR"
            };
            this.fireDataEvent("showInLogger", retryMsgData);
            this.__unresponsiveRetries--;
            const interval = Math.floor(Math.random() * 5000) + 3000;
            setTimeout(() => this.__nodeState(), interval);
          } else {
            this.getStatus().setInteractive("failed");
            osparc.FlashMessenger.getInstance().logAs(this.tr("There was an error starting") + " " + this.getLabel(), "ERROR");
          }
        });
    },

    __onNodeState: function(data, starting=true) {
      const serviceState = data["service_state"];
      const nodeId = data["service_uuid"];
      const status = this.getStatus();
      switch (serviceState) {
        case "idle": {
          status.setInteractive(serviceState);
          if (starting && this.__unresponsiveRetries>0) {
            // a bit of a hack. We will get rid of it when the backend pushes the states
            this.__unresponsiveRetries--;
            const interval = 2000;
            qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          }
          break;
        }
        case "pending": {
          if (data["service_message"]) {
            const serviceName = this.getLabel();
            const serviceMessage = data["service_message"];
            const msg = `The service "${serviceName}" is waiting for available ` +
              `resources. Please inform support and provide the following message ` +
              `in case this does not resolve in a few minutes: "${nodeId}" ` +
              `reported "${serviceMessage}"`;
            const msgData = {
              nodeId: this.getNodeId(),
              msg: msg,
              level: "INFO"
            };
            this.fireDataEvent("showInLogger", msgData);
          }
          status.setInteractive(serviceState);
          const interval = 10000;
          qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          break;
        }
        case "stopping":
        case "unknown":
        case "starting":
        case "pulling": {
          status.setInteractive(serviceState);
          const interval = 5000;
          qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          break;
        }
        case "running": {
          if (nodeId !== this.getNodeId()) {
            return;
          }
          if (!starting) {
            status.setInteractive("stopping");
            const interval = 5000;
            qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
            break;
          }
          const {
            srvUrl,
            isDynamicV2
          } = osparc.utils.Utils.computeServiceUrl(data);
          this.setDynamicV2(isDynamicV2);
          if (srvUrl) {
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
            nodeId: this.getNodeId(),
            msg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          return;
        }
        default:
          console.error(serviceState, "service state not supported");
          break;
      }
    },

    __waitForServiceReady: function(srvUrl) {
      this.getStatus().setInteractive("connecting");

      if (this.__retriesLeft === 0) {
        return;
      }

      const retry = () => {
        this.__retriesLeft--;

        // Check if node is still there
        if (this.getWorkbench().getNode(this.getNodeId()) === null) {
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
      this.setServiceUrl(srvUrl);
      this.getStatus().setInteractive("ready");
      const msg = "Service ready on " + srvUrl;
      const msgData = {
        nodeId: this.getNodeId(),
        msg,
        level: "INFO"
      };
      this.fireDataEvent("showInLogger", msgData);
      this.__restartIFrame();
      this.callRetrieveInputs();
    },

    __restartIFrame: function() {
      if (this.getServiceUrl() !== null) {
        // restart button pushed
        if (this.getIFrame().getSource().includes(this.getServiceUrl())) {
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
      const status = this.getStatus().getInteractive();
      // it might have been stopped
      if (status === "ready") {
        this.getIFrame().resetSource();
        this.getIFrame().setSource(this.getServiceUrl());

        // fire event to force switching to iframe's content:
        // it is required in those cases where the native 'load' event isn't triggered (voila)
        this.fireEvent("iframeChanged");
      }
    }
  }
});
