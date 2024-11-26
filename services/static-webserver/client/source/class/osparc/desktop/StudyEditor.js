/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.StudyEditor", {
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    const viewsStack = this.__viewsStack = new qx.ui.container.Stack();
    const workbenchView = this.__workbenchView = new osparc.desktop.WorkbenchView();
    viewsStack.add(workbenchView);
    const slideshowView = this.__slideshowView = new osparc.desktop.SlideshowView();
    viewsStack.add(slideshowView);

    [
      "collapseNavBar",
      "expandNavBar",
      "backToDashboardPressed"
    ].forEach(signalName => {
      workbenchView.addListener(signalName, () => this.fireEvent(signalName));
      slideshowView.addListener(signalName, () => this.fireEvent(signalName));
    });

    workbenchView.addListener("slidesEdit", () => this.__editSlides(), this);
    workbenchView.addListener("slidesAppStart", () => this.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]), this);
    slideshowView.addListener("slidesStop", () => this.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]), this);

    workbenchView.addListener("takeSnapshot", () => this.__takeSnapshot(), this);
    workbenchView.addListener("takeSnapshot", () => this.__takeSnapshot(), this);
    workbenchView.addListener("showSnapshots", () => this.__showSnapshots(), this);
    workbenchView.addListener("createIterations", () => this.__createIterations(), this);
    workbenchView.addListener("showIterations", () => this.__showIterations(), this);

    workbenchView.addListener("changeSelectedNode", e => {
      if (this.__nodesSlidesTree) {
        const nodeId = e.getData();
        this.__nodesSlidesTree.changeSelectedNode(nodeId);
      }
    });


    const wbAppear = new Promise(resolve => workbenchView.addListenerOnce("appear", resolve, false));
    const ssAppear = new Promise(resolve => slideshowView.addListenerOnce("appear", resolve, false));
    Promise.all([wbAppear, ssAppear]).then(() => {
      // both are ready
      workbenchView.getCollapseWithUserMenu().bind("collapsed", slideshowView.getCollapseWithUserMenu(), "collapsed");
      slideshowView.getCollapseWithUserMenu().bind("collapsed", workbenchView.getCollapseWithUserMenu(), "collapsed");
    });

    slideshowView.addListener("startPartialPipeline", e => {
      const partialPipeline = e.getData();
      this.__startPipeline(partialPipeline);
    }, this);
    slideshowView.addListener("stopPipeline", this.__stopPipeline, this);


    const startStopButtons = workbenchView.getStartStopButtons();
    startStopButtons.addListener("startPipeline", () => this.__startPipeline([]), this);
    startStopButtons.addListener("startPartialPipeline", () => {
      const partialPipeline = this.getPageContext() === "workbench" ? this.__workbenchView.getSelectedNodeIDs() : this.__slideshowView.getSelectedNodeIDs();
      this.__startPipeline(partialPipeline);
    }, this);
    startStopButtons.addListener("stopPipeline", () => this.__stopPipeline(), this);


    this._addToMainLayout(viewsStack, {
      flex: 1
    });

    this.__updatingStudy = 0;
  },

  events: {
    "forceBackToDashboard": "qx.event.type.Event",
    "backToDashboardPressed": "qx.event.type.Event",
    "userIdled": "qx.event.type.Event",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event",
    "startSnapshot": "qx.event.type.Data",
    "startIteration": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: true,
      apply: "__applyStudy",
      event: "changeStudy"
    },

    pageContext: {
      check: ["workbench", "guided", "app"],
      init: null,
      nullable: false,
      event: "changePageContext",
      apply: "__applyPageContext"
    }
  },

  statics: {
    AUTO_SAVE_INTERVAL: 3000,
    READ_ONLY_TEXT: qx.locale.Manager.tr("You do not have writing permissions.<br>Your changes will not be saved.")
  },

  members: {
    __study: null,
    __settingStudy: null,
    __viewsStack: null,
    __workbenchView: null,
    __slideshowView: null,
    __autoSaveTimer: null,
    __studyEditorIdlingTracker: null,
    __studyDataInBackend: null,
    __updatingStudy: null,
    __updateThrottled: null,
    __nodesSlidesTree: null,

    setStudyData: function(studyData) {
      if (this.__settingStudy) {
        return;
      }
      this.__settingStudy = true;

      this._showLoadingPage(this.tr("Starting") + " " + studyData.name);

      // Before starting a study, make sure the latest version is fetched
      const params = {
        url: {
          "studyId": studyData.uuid
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(latestStudyData => {
          const study = new osparc.data.model.Study(latestStudyData);
          this.setStudy(study);
        });
    },

    __applyStudy: function(study) {
      this.__settingStudy = false;

      this._showLoadingPage(this.tr("Opening ") + (study.getName() || osparc.product.Utils.getStudyAlias({firstUpperCase: true})));

      const store = osparc.store.Store.getInstance();
      store.setCurrentStudy(study);

      this.__reloadSnapshotsAndIterations();

      study.openStudy()
        .then(studyData => {
          this.__setStudyDataInBackend(studyData);

          this.__workbenchView.setStudy(study);
          this.__slideshowView.setStudy(study);

          // wait until the workbench is deserialized to move to the next step
          if (study.getWorkbench().isDeserialized()) {
            this.__initStudy(study);
          } else {
            study.getWorkbench().addListener("changeDeserialized", e => {
              if (e.getData()) {
                this.__initStudy(study);
              }
            }, this);
          }
        })
        .catch(err => {
          console.error(err);
          let msg = "";
          if ("status" in err && err["status"] == 409) { // max_open_studies_per_user
            msg = err["message"];
          } else if ("status" in err && err["status"] == 423) { // Locked
            msg = study.getName() + this.tr(" is already opened");
          } else {
            msg = this.tr("Error opening study");
            if ("message" in err) {
              msg += "<br>" + err["message"];
            }
          }
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
          this.fireEvent("forceBackToDashboard");
        })
        .finally(() => this._hideLoadingPage());

      this.__updatingStudy = 0;
    },

    __initStudy: function(study) {
      this.__attachSocketEventHandlers();

      study.initStudy();

      if (osparc.product.Utils.hasIdlingTrackerEnabled()) {
        this.__startIdlingTracker();
      }

      // Count dynamic services.
      // If it is larger than PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES, dynamics won't start -> Flash Message
      const maxNumber = osparc.store.StaticInfo.getInstance().getMaxNumberDyNodes();
      const dontCheck = study.getDisableServiceAutoStart();
      if (maxNumber && !dontCheck) {
        const nodes = study.getWorkbench().getNodes();
        const nDynamics = Object.values(nodes).filter(node => node.isDynamic()).length;
        if (nDynamics > maxNumber) {
          let msg = this.tr("The Study contains more than ") + maxNumber + this.tr(" Interactive services.");
          msg += "<br>";
          msg += this.tr("Please start them manually.");
          osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
        }
      }

      if (osparc.data.model.Study.canIWrite(study.getAccessRights())) {
        this.__startAutoSaveTimer();
      } else {
        const msg = this.self().READ_ONLY_TEXT;
        osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
      }

      const pageContext = study.getUi().getMode();
      switch (pageContext) {
        case "guided":
        case "app":
          this.__slideshowView.startSlides();
          break;
        default:
          this.__workbenchView.openFirstNode();
          break;
      }
      this.addListener("changePageContext", e => {
        const pageCxt = e.getData();
        study.getUi().setMode(pageCxt);
      });
      this.setPageContext(pageContext);

      const workbench = study.getWorkbench();
      workbench.addListener("retrieveInputs", e => {
        const data = e.getData();
        const node = data["node"];
        const portKey = data["portKey"];
        this.__updatePipelineAndRetrieve(node, portKey);
      }, this);

      workbench.addListener("openNode", e => {
        const nodeId = e.getData();
        this.nodeSelected(nodeId);
      }, this);

      workbench.addListener("updateStudyDocument", () => this.updateStudyDocument());
      workbench.addListener("restartAutoSaveTimer", () => this.__restartAutoSaveTimer());
    },

    __setStudyDataInBackend: function(studyData) {
      this.__studyDataInBackend = osparc.data.model.Study.deepCloneStudyObject(studyData, true);

      // remove the runHash, this.__studyDataInBackend is only used for diff comparison and the frontend doesn't keep it
      Object.keys(this.__studyDataInBackend["workbench"]).forEach(nodeId => {
        if ("runHash" in this.__studyDataInBackend["workbench"][nodeId]) {
          delete this.__studyDataInBackend["workbench"][nodeId]["runHash"];
        }
      });
    },

    __attachSocketEventHandlers: function() {
      // Listen to socket events
      this.__listenToLogger();
      this.__listenToProgress();
      this.__listenToNodeUpdated();
      this.__listenToNodeProgress();
      this.__listenToNoMoreCreditsEvents();
      this.__listenToEvent();
      this.__listenToServiceStatus();
      this.__listenToStatePorts();
    },

    __listenToLogger: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      if (!socket.slotExists("logger")) {
        socket.on("logger", data => {
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy()) {
            if (this.getStudy().getUuid() !== data["project_id"]) {
              // Filter out logs from other studies
              return;
            }
            const nodeId = data["node_id"];
            const messages = data.messages;
            const logLevelMap = osparc.widget.logger.LoggerView.LOG_LEVEL_MAP;
            const logLevel = ("log_level" in data) ? logLevelMap[data["log_level"]] : "INFO";

            if (this.__workbenchView) {
              this.__workbenchView.logsToLogger(nodeId, messages, logLevel);
            }
          }
        }, this);
      }
      socket.emit("logger");
    },

    __listenToProgress: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      const slotName2 = "progress";
      if (!socket.slotExists(slotName2)) {
        socket.on(slotName2, jsonString => {
          const data = JSON.parse(jsonString);
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy()) {
            if (this.getStudy().getUuid() !== data["project_id"]) {
              // Filter out logs from other studies
              return;
            }
            const nodeId = data["node_id"];
            const progress = Number.parseFloat(data["progress"]).toFixed(4);
            const workbench = this.getStudy().getWorkbench();
            const node = workbench.getNode(nodeId);
            if (node) {
              node.getStatus().setProgress(progress);
            } else if (osparc.data.Permissions.getInstance().isTester()) {
              console.log("Ignored ws 'progress' msg", data);
            }
          }
        }, this);
      }
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

    __listenToNoMoreCreditsEvents: function() {
      const slotName = "serviceNoMoreCredits";
      const flashMessageDisplayDuration = 10000;

      const socket = osparc.wrapper.WebSocket.getInstance();
      const ttlMap = new osparc.data.TTLMap(flashMessageDisplayDuration);
      const store = osparc.store.Store.getInstance();

      if (!socket.slotExists(slotName)) {
        socket.on(slotName, noMoreCredits => {
          // stop service
          const nodeId = noMoreCredits["node_id"];
          const workbench = this.getStudy().getWorkbench();
          workbench.getNode(nodeId).requestStopNode();

          // display flash message if not showing
          const walletId = noMoreCredits["wallet_id"];
          if (ttlMap.hasRecentEntry(walletId)) {
            return;
          }
          ttlMap.addOrUpdateEntry(walletId);
          const usedWallet = store.getWallets().find(wallet => wallet.getWalletId() === walletId);
          const walletName = usedWallet.getName();
          const text = `Wallet "${walletName}", running your service(s) has run out of credits. Stopping service(s) gracefully.`;
          osparc.FlashMessenger.getInstance().logAs(this.tr(text), "ERROR", flashMessageDisplayDuration);
        }, this);
      }
    },

    __listenToEvent: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      // callback for events
      if (!socket.slotExists("event")) {
        socket.on("event", data => {
          const { action, "node_id": nodeId } = data
          if (Object.prototype.hasOwnProperty.call(data, "project_id") && this.getStudy()) {
            if (this.getStudy().getUuid() !== data["project_id"]) {
              // Filter out logs from other studies
              return;
            }
            if (action == "RELOAD_IFRAME") {
              // TODO: maybe reload iframe in the future
              // for now a message is displayed to the user
              const workbench = this.getStudy().getWorkbench();
              const node = workbench.getNode(nodeId);
              const label = node.getLabel();
              const text = `New inputs for service ${label}. Please reload to refresh service.`;
              osparc.FlashMessenger.getInstance().logAs(text, "INFO");
            }
          }
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
    },

    __listenToStatePorts: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (!socket.slotExists("stateInputPorts")) {
        socket.on("stateInputPorts", data => {
          this.__statePortReceived(data, "stateInputPorts");
        }, this);
      }
      if (!socket.slotExists("stateOutputPorts")) {
        socket.on("stateOutputPorts", data => {
          this.__statePortReceived(data, "stateOutputPorts");
        }, this);
      }
    },

    __statePortReceived: function(socketData, msgName) {
      const studyId = socketData["project_id"];
      if (this.getStudy().getUuid() !== studyId) {
        return;
      }

      const nodeId = socketData["node_id"];
      const workbench = this.getStudy().getWorkbench();
      const node = workbench.getNode(nodeId);
      if (!node) {
        if (osparc.data.Permissions.getInstance().isTester()) {
          console.log("Ignored ws 'stateInputPorts' msg", socketData);
        }
        return;
      }

      const propsForm = node.getPropsForm();
      if (msgName === "stateInputPorts" && propsForm) {
        const portId = socketData["port_key"];
        const status = socketData["status"];
        switch (status) {
          case "DOWNLOAD_STARTED":
            propsForm.retrievingPortData(
              portId,
              osparc.form.renderer.PropForm.RETRIEVE_STATUS.downloading
            );
            break;
          case "DOWNLOAD_FINISHED_SUCCESSFULLY":
            propsForm.retrievedPortData(portId, true);
            break;
          case "DOWNLOAD_WAS_ABORTED":
          case "DOWNLOAD_FINISHED_WITH_ERROR":
            propsForm.retrievedPortData(portId, false);
            break;
        }
      }

      const outputsForm = node.getOutputsForm();
      if (msgName === "stateOutputPorts" && outputsForm) {
        const portId = socketData["port_key"];
        const status = socketData["status"];
        switch (status) {
          case "UPLOAD_STARTED":
            outputsForm.setRetrievingStatus(
              portId,
              osparc.form.renderer.PropForm.RETRIEVE_STATUS.uploading
            );
            break;
          case "UPLOAD_FINISHED_SUCCESSFULLY":
            outputsForm.setRetrievingStatus(
              portId,
              osparc.form.renderer.PropForm.RETRIEVE_STATUS.succeed
            );
            break;
          case "UPLOAD_WAS_ABORTED":
          case "UPLOAD_FINISHED_WITH_ERROR":
            outputsForm.setRetrievingStatus(
              portId,
              osparc.form.renderer.PropForm.RETRIEVE_STATUS.failed
            );
            break;
        }
      }
    },

    __reloadSnapshotsAndIterations: function() {
      const isVCDisabled = osparc.utils.DisabledPlugins.isVersionControlDisabled();
      if (!isVCDisabled) {
        const store = osparc.store.Store.getInstance();
        store.invalidate("snapshots");
        store.invalidate("iterations");

        const study = this.getStudy();
        study.getSnapshots()
          .then(snapshots => {
            store.setSnapshots(snapshots);
            if (snapshots.length) {
              const isMMDisabled = osparc.utils.DisabledPlugins.isMetaModelingDisabled();
              if (!isMMDisabled) {
                study.getIterations()
                  .then(iterations => {
                    store.setIterations(iterations);
                  });
              }
            }
          });
      }
    },

    __editSlides: function() {
      if (this.getPageContext() !== osparc.navigation.NavigationBar.PAGE_CONTEXT[1]) {
        return;
      }

      const study = this.getStudy();
      const nodesSlidesTree = this.__nodesSlidesTree = new osparc.widget.NodesSlidesTree(study);
      const title = this.tr("Edit App Mode");
      const nNodes = Object.keys(study.getWorkbench().getNodes()).length;
      const win = osparc.ui.window.Window.popUpInWindow(nodesSlidesTree, title, 370, Math.min(350, 200+(30*nNodes))).set({
        modal: false,
        clickAwayClose: false
      });
      nodesSlidesTree.addListener("changeSelectedNode", e => {
        const nodeId = e.getData();
        this.__workbenchView.getNodesTree().nodeSelected(nodeId);
        this.__workbenchView.getWorkbenchUI().nodeSelected(nodeId);
      });
      nodesSlidesTree.addListener("finished", () => {
        const slideshow = study.getUi().getSlideshow();
        slideshow.fireEvent("changeSlideshow");
        this.__nodesSlidesTree = null;
        win.close();
      });
    },


    // ------------------ START/STOP PIPELINE ------------------
    __startPipeline: function(partialPipeline = []) {
      if (!osparc.data.Permissions.getInstance().canDo("study.start", true)) {
        return;
      }

      this.getStudy().setPipelineRunning(true);
      this.updateStudyDocument()
        .then(() => {
          this.__requestStartPipeline(this.getStudy().getUuid(), partialPipeline);
        })
        .catch(() => {
          this.getStudyLogger().error(null, "Run failed");
          this.getStudy().setPipelineRunning(false);
        });
    },

    __requestStartPipeline: function(studyId, partialPipeline = [], forceRestart = false) {
      const url = "/computations/" + encodeURIComponent(studyId) + ":start";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", this.__onPipelineSubmitted, this);
      req.addListener("error", () => {
        this.getStudyLogger().error(null, "Error submitting pipeline");
        this.getStudy().setPipelineRunning(false);
      }, this);
      req.addListener("fail", async e => {
        if (e.getTarget().getStatus() == "409") {
          this.getStudyLogger().error(null, "Pipeline is already running");
        } else if (e.getTarget().getStatus() == "422") {
          this.getStudyLogger().info(null, "The pipeline is up-to-date");
          const msg = this.tr("The pipeline is up-to-date. Do you want to re-run it?");
          const win = new osparc.ui.window.Confirmation(msg).set({
            caption: this.tr("Re-run"),
            confirmText: this.tr("Run"),
            confirmAction: "create"
          });
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__requestStartPipeline(studyId, partialPipeline, true);
            }
          }, this);
        } else if (e.getTarget().getStatus() == "402") {
          const msg = await e.getTarget().getResponse().error.errors[0].message;
          osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
        } else {
          this.getStudyLogger().error(null, "Failed submitting pipeline");
        }
        this.getStudy().setPipelineRunning(false);
      }, this);

      const requestData = {
        "subgraph": partialPipeline,
        "force_restart": forceRestart
      };
      const startStopButtonsWB = this.__workbenchView.getStartStopButtons();
      if (startStopButtonsWB.getClusterId() !== null) {
        requestData["cluster_id"] = startStopButtonsWB.getClusterId();
      }
      req.setRequestData(requestData);
      req.send();
      if (partialPipeline.length) {
        this.getStudyLogger().info(null, "Starting partial pipeline");
      } else {
        this.getStudyLogger().info(null, "Starting pipeline");
      }

      return true;
    },

    __onPipelineSubmitted: function(e) {
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["pipeline_id"];
      const iterationRefIds = resp.data["ref_ids"];
      this.getStudyLogger().debug(null, "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.getStudyLogger().error(null, "Submission failed");
      } else {
        if (iterationRefIds) {
          this.__reloadSnapshotsAndIterations();
        }
        this.getStudyLogger().info(null, "Pipeline started");
        /* If no projectStateUpdated comes in 60 seconds, client must
        check state of pipeline and update button accordingly. */
        const timer = setTimeout(() => {
          osparc.store.Store.getInstance().getStudyState(pipelineId);
        }, 60000);
        const socket = osparc.wrapper.WebSocket.getInstance();
        socket.getSocket().once("projectStateUpdated", ({ "project_uuid": projectUuid }) => {
          if (projectUuid === pipelineId) {
            clearTimeout(timer);
          }
        });
      }
    },

    __stopPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.stop", true)) {
        return;
      }

      this.__requestStopPipeline(this.getStudy().getUuid());
    },

    __requestStopPipeline: function(studyId) {
      const url = "/computations/" + encodeURIComponent(studyId) + ":stop";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", () => this.getStudyLogger().debug(null, "Pipeline aborting"), this);
      req.addListener("error", () => this.getStudyLogger().error(null, "Error stopping pipeline"), this);
      req.addListener("fail", () => this.getStudyLogger().error(null, "Failed stopping pipeline"), this);
      req.send();

      this.getStudyLogger().info(null, "Stopping pipeline");
      return true;
    },
    // ------------------ START/STOP PIPELINE ------------------

    __updatePipelineAndRetrieve: function(node, portKey = null) {
      this.updateStudyDocument()
        .then(() => {
          if (node) {
            this.getStudyLogger().debug(node.getNodeId(), "Retrieving inputs");
            node.retrieveInputs(portKey);
          } else {
            this.getStudyLogger().debug(null, "Retrieving inputs");
          }
        });
      this.getStudyLogger().debug(null, "Updating pipeline");
    },

    nodeSelected: function(nodeId) {
      this.__workbenchView.nodeSelected(nodeId);
      this.__slideshowView.nodeSelected(nodeId);
    },

    getStudyLogger: function() {
      return this.__workbenchView.getLogger();
    },

    __applyPageContext: function(newCtxt) {
      switch (newCtxt) {
        case "workbench":
          this.__viewsStack.setSelection([this.__workbenchView]);
          if (this.getStudy() && this.getStudy().getUi()) {
            this.__workbenchView.nodeSelected(this.getStudy().getUi().getCurrentNodeId());
          }
          break;
        case "guided":
        case "app":
          this.__viewsStack.setSelection([this.__slideshowView]);
          if (this.getStudy() && this.getStudy().getUi()) {
            this.__slideshowView.startSlides();
          }
          break;
      }
    },

    __takeSnapshot: function() {
      const editSnapshotView = new osparc.snapshots.EditSnapshotView();
      const tagCtrl = editSnapshotView.getChildControl("tags");
      const study = this.getStudy();
      study.getSnapshots()
        .then(snapshots => {
          tagCtrl.setValue("V"+snapshots.length);
        });
      const title = this.tr("Take Snapshot");
      const win = osparc.ui.window.Window.popUpInWindow(editSnapshotView, title, 400, 180);
      editSnapshotView.addListener("takeSnapshot", () => {
        const tag = editSnapshotView.getTag();
        const message = editSnapshotView.getMessage();
        const params = {
          url: {
            "studyId": study.getUuid()
          },
          data: {
            "tag": tag,
            "message": message
          }
        };
        osparc.data.Resources.fetch("snapshots", "takeSnapshot", params)
          .then(data => {
            const store = osparc.store.Store.getInstance();
            store.getSnapshots().push(data);
          })
          .catch(err => osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR"));

        win.close();
      }, this);
      editSnapshotView.addListener("cancel", () => win.close(), this);
    },

    __showSnapshots: function() {
      const study = this.getStudy();
      const snapshots = new osparc.snapshots.SnapshotsView(study);
      const title = this.tr("Checkpoints");
      const win = osparc.ui.window.Window.popUpInWindow(snapshots, title, 1000, 500);
      snapshots.addListener("openSnapshot", e => {
        win.close();
        const snapshotId = e.getData();
        this.fireDataEvent("startSnapshot", snapshotId);
      });
    },

    __createIterations: function() {
      console.log("createIterations not implemented yet");
    },

    __showIterations: function() {
      const study = this.getStudy();
      const iterations = new osparc.snapshots.IterationsView(study);
      const title = this.tr("Iterations");
      const win = osparc.ui.window.Window.popUpInWindow(iterations, title, 1000, 500);
      iterations.addListener("openIteration", e => {
        win.close();
        const studyId = e.getData();
        this.fireDataEvent("startIteration", studyId);
      });
      win.addListener("close", () => {
        iterations.unlistenToNodeUpdated();
        this.__listenToNodeUpdated();
      }, this);
    },

    __startIdlingTracker: function() {
      if (this.__studyEditorIdlingTracker) {
        this.__studyEditorIdlingTracker.stop();
        this.__studyEditorIdlingTracker = null;
      }
      const studyEditorIdlingTracker = this.__studyEditorIdlingTracker = new osparc.desktop.StudyEditorIdlingTracker(this.getStudy().getUuid());
      studyEditorIdlingTracker.addListener("userIdled", () => this.fireEvent("userIdled"));
      studyEditorIdlingTracker.start();
    },

    __stopIdlingTracker: function() {
      if (this.__studyEditorIdlingTracker) {
        this.__studyEditorIdlingTracker.stop();
        this.__studyEditorIdlingTracker = null;
      }
    },

    __startAutoSaveTimer: function() {
      // Save every 3 seconds
      const timer = this.__autoSaveTimer = new qx.event.Timer(this.self().AUTO_SAVE_INTERVAL);
      timer.addListener("interval", () => {
        if (!osparc.wrapper.WebSocket.getInstance().isConnected()) {
          return;
        }
        this.__checkStudyChanges();
      }, this);
      timer.start();
    },

    __stopAutoSaveTimer: function() {
      if (this.__autoSaveTimer && this.__autoSaveTimer.isEnabled()) {
        this.__autoSaveTimer.stop();
        this.__autoSaveTimer.setEnabled(false);
      }
    },

    __restartAutoSaveTimer: function() {
      if (this.__autoSaveTimer && this.__autoSaveTimer.isEnabled()) {
        this.__autoSaveTimer.restart();
      }
    },

    __stopTimers: function() {
      this.__stopIdlingTracker();
      this.__stopAutoSaveTimer();
    },

    __getStudyDiffs: function() {
      const newObj = this.getStudy().serialize();
      const delta = osparc.wrapper.JsonDiffPatch.getInstance().diff(this.__studyDataInBackend, newObj);
      if (delta) {
        // lastChangeDate and creationDate should not be taken into account as data change
        delete delta["creationDate"];
        delete delta["lastChangeDate"];
        return delta;
      }
      return {};
    },

    didStudyChange: function() {
      const studyDiffs = this.__getStudyDiffs();
      return Boolean(Object.keys(studyDiffs).length);
    },

    __checkStudyChanges: function() {
      if (this.didStudyChange()) {
        if (this.__updatingStudy > 0) {
          // throttle update
          this.__updateThrottled = true;
        } else {
          this.updateStudyDocument();
        }
      }
    },

    updateStudyDocument: function() {
      if (!osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights())) {
        return new Promise(resolve => {
          resolve();
        });
      }

      this.__updatingStudy++;
      const studyDiffs = this.__getStudyDiffs();
      return this.getStudy().patchStudyDelayed(studyDiffs)
        .then(studyData => this.__setStudyDataInBackend(studyData))
        .catch(error => {
          if ("status" in error && error.status === 409) {
            console.log("Flash message blocked"); // Workaround for osparc-issues #1189
          } else {
            console.error(error);
            osparc.FlashMessenger.getInstance().logAs(this.tr("Error saving the study"), "ERROR");
          }
          this.getStudyLogger().error(null, "Error updating pipeline");
          // Need to throw the error to be able to handle it later
          throw error;
        })
        .finally(() => {
          this.__updatingStudy--;
          if (this.__updateThrottled && this.__updatingStudy === 0) {
            this.__updateThrottled = false;
            this.updateStudyDocument();
          }
        });
    },

    __closeStudy: function() {
      const params = {
        url: {
          "studyId": this.getStudy().getUuid()
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      osparc.data.Resources.fetch("studies", "close", params)
        .catch(err => console.error(err));
    },

    closeEditor: function() {
      this.__stopTimers();
      if (this.getStudy()) {
        this.getStudy().stopStudy();
        this.__closeStudy();
      }
      const clusterMiniView = this.__workbenchView.getStartStopButtons().getChildControl("cluster-mini-view");
      if (clusterMiniView) {
        clusterMiniView.setClusterId(null);
      }
      osparc.utils.Utils.closeHangingWindows();
    },

    /**
     * Destructor
     */
    destruct: function() {
      osparc.store.Store.getInstance().setCurrentStudy(null);
      this.__stopTimers();
    }
  }
});
