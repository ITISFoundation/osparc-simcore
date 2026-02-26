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
      const partialPipeline = this.getStudy().getUi().getMode() === "app" ? this.__slideshowView.getSelectedNodeIDs() : this.__workbenchView.getSelectedNodeIDs();
      this.__startPipeline(partialPipeline);
    }, this);
    startStopButtons.addListener("stopPipeline", () => this.__stopPipeline(), this);


    this._addToMainLayout(viewsStack, {
      flex: 1
    });

    this.__updatingStudy = 0;
    this.__throttledPatchPending = false;
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
  },

  statics: {
    AUTO_SAVE_INTERVAL: 3000,
    DIFF_CHECK_INTERVAL: 300,
    THROTTLE_PATCH_TIME: 500,
    READ_ONLY_TEXT: qx.locale.Manager.tr("You do not have writing permissions.<br>Your changes will not be saved."),

    curateBackendProjectDocument: function(projectDocument) {
      // ignore the ``state`` property, it has its own channel
      [
        "state",
      ].forEach(prop => {
        delete projectDocument[prop];
      });
      // in order to pair it the with frontend's node serialization
      // remove null entries
      // remove state entries
      Object.keys(projectDocument["workbench"]).forEach(nodeId => {
        const node = projectDocument["workbench"][nodeId];
        Object.keys(node).forEach(nodeProp => {
          if (nodeProp === "state") {
            delete node[nodeProp];
          }
          if (node[nodeProp] === null) {
            delete node[nodeProp];
          }
        });
      });
      delete projectDocument["ui"]["icon"];
      delete projectDocument["ui"]["templateType"];
    },

    curateFrontendProjectDocument: function(myStudy) {
      // the updatedStudy model doesn't contain the following properties
      [
        "accessRights",
        "creationDate",
        "folderId",
        "prjOwner",
        "tags",
        "trashedBy",
      ].forEach(prop => {
        delete myStudy[prop];
      });
    }
  },

  members: {
    __settingStudy: null,
    __viewsStack: null,
    __workbenchView: null,
    __slideshowView: null,
    __studyEditorIdlingTracker: null,
    __lastSyncedProjectDocument: null,
    __lastSyncedProjectVersion: null,
    __pendingProjectData: null,
    __applyProjectDocumentTimer: null,
    __updatingStudy: null,
    __updateThrottled: null,
    __nodesSlidesTree: null,
    __throttledPatchPending: null,
    __blockUpdates: null,

    setStudyData: function(studyData) {
      if (this.__settingStudy) {
        return;
      }
      this.__settingStudy = true;

      this._showLoadingPage(this.tr("Starting") + " " + studyData.name);

      // Before starting a study, make sure the latest version is fetched
      osparc.store.Study.getInstance().getOne(studyData.uuid)
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
          this.__setLastSyncedProjectDocument(studyData);

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

          study.getUi().addListener("changeMode", e => {
            this.__uiModeChanged(e.getData(), e.getOldData());
          });
        })
        .catch(err => {
          console.error(err);
          let msg = "";
          if ("status" in err && err["status"]) {
            if (err["status"] == 402) {
              msg = err["message"];
              osparc.study.Utils.extractDebtFromError(study.getUuid(), err);
            } else if (err["status"] == 409) { // max_open_studies_per_user
              msg = err["message"];
            } else if (err["status"] == 423) { // Locked
              msg = study.getName() + this.tr(" is already opened");
            }
          }
          if (!msg) {
            msg = this.tr("Error opening study");
            if ("message" in err) {
              msg += "<br>" + err["message"];
            }
          }
          osparc.FlashMessenger.logError(msg);
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
      const maxNumber = osparc.store.StaticInfo.getMaxNumberDyNodes();
      const dontCheck = study.getDisableServiceAutoStart();
      if (maxNumber && !dontCheck) {
        const nodes = study.getWorkbench().getNodes();
        const nDynamics = Object.values(nodes).filter(node => node.isDynamic()).length;
        if (nDynamics > maxNumber) {
          let msg = this.tr("The Study contains more than ") + maxNumber + this.tr(" Interactive services.");
          msg += "<br>";
          msg += this.tr("Please start them manually.");
          osparc.FlashMessenger.logAs(msg, "WARNING");
        }
      }

      if (!osparc.data.model.Study.canIWrite(study.getAccessRights())) {
        const msg = this.self().READ_ONLY_TEXT;
        osparc.FlashMessenger.logAs(msg, "WARNING");
      }


      const uiMode = study.getUi().getMode();
      this.__uiModeChanged(uiMode);

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

      study.listenToChanges(); // this includes the listener on the workbench and ui
      study.addListener("projectDocumentChanged", e => this.__projectDocumentChanged(e.getData()), this);

      if (osparc.utils.DisabledPlugins.isRTCEnabled()) {
        this.__listenToProjectDocument();
      }
    },

    __setLastSyncedProjectDocument: function(studyData) {
      this.__lastSyncedProjectDocument = osparc.data.model.Study.deepCloneStudyObject(studyData, true);

      // remove the runHash, this.__lastSyncedProjectDocument is only used for diff comparison and the frontend doesn't keep it
      Object.keys(this.__lastSyncedProjectDocument["workbench"]).forEach(nodeId => {
        if ("runHash" in this.__lastSyncedProjectDocument["workbench"][nodeId]) {
          delete this.__lastSyncedProjectDocument["workbench"][nodeId]["runHash"];
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
      this.__listenToServiceCustomEvents();
      this.__listenToServiceStatus();
      this.__listenToStatePorts();

      const socket = osparc.wrapper.WebSocket.getInstance();
      [
        "connect",
        "reconnect",
      ].forEach(evtName => {
        socket.addListener(evtName, () => {
          // after a reconnect, re-sync the project document
          console.log("WebSocket reconnected, re-syncing project document");
          const studyId = this.getStudy().getUuid();
          osparc.store.Study.getInstance().getOne(studyId)
            .then(latestStudyData => {
              const latestData = {
                "version": this.__lastSyncedProjectVersion, // do not increase the version
                "document": latestStudyData,
              };
              this.__applyProjectDocument(latestData);
            })
            .catch(err => {
              console.error("Failed to re-sync project document after WebSocket reconnect:", err);
            });
        });
      });
    },

    __listenToProjectDocument: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();

      if (!socket.slotExists("projectDocument:updated")) {
        socket.on("projectDocument:updated", data => {
          if (data["projectId"] === this.getStudy().getUuid()) {
            if (data["clientSessionId"] && data["clientSessionId"] === osparc.utils.Utils.getClientSessionID()) {
              // ignore my own updates
              console.debug("ProjectDocument Discarded: My own", data);
              return;
            }
            this.__projectDocumentReceived(data);
          }
        }, this);
      }
    },

    __projectDocumentReceived: function(data) {
      const documentVersion = data["version"];

      // Ignore outdated updates
      if (this.__lastSyncedProjectVersion && documentVersion <= this.__lastSyncedProjectVersion) {
        // ignore old updates
        console.debug("ProjectDocument Discarded: Ignoring old", data);
        return;
      }

      // Always keep the latest version in pending buffer
      if (!this.__pendingProjectData || documentVersion > (this.__pendingProjectData.version || 0)) {
        this.__pendingProjectData = data;
      }

      // Reset the timer if it's already running
      if (this.__applyProjectDocumentTimer) {
        console.debug("ProjectDocument Discarded: Resetting applyProjectDocument timer");
        clearTimeout(this.__applyProjectDocumentTimer);
      }

      // Throttle applying updates
      this.__applyProjectDocumentTimer = setTimeout(() => {
        if (!this.__pendingProjectData) {
          return;
        }
        this.__applyProjectDocumentTimer = null;

        // Apply the latest buffered project document
        const latestData = this.__pendingProjectData;
        this.__pendingProjectData = null;

        this.__applyProjectDocument(latestData);
      }, 3*this.self().THROTTLE_PATCH_TIME);
      // make it 3 times longer.
      // when another client adds a node:
      // - there is a POST call
      // - then (after the throttle) a PATCH on its position
      // without waiting for it 3 times, this client might place it on the default 0,0
    },

    __applyProjectDocument: function(data) {
      console.debug("ProjectDocument applying:", data);
      this.__lastSyncedProjectVersion = data["version"];
      const updatedProjectDocument = data["document"];

      // curate projectDocument:updated document
      this.self().curateBackendProjectDocument(updatedProjectDocument);

      const myStudy = this.getStudy().serialize();
      // curate myStudy
      this.self().curateFrontendProjectDocument(myStudy);

      this.__blockUpdates = true;
      const delta = this.__calculateDelta(myStudy, updatedProjectDocument);
      const jsonPatches = osparc.wrapper.JsonDiffPatch.getInstance().deltaToJsonPatches(delta);
      const uiPatches = [];
      const workbenchPatches = [];
      const studyPatches = [];
      for (const jsonPatch of jsonPatches) {
        if (jsonPatch.path.startsWith('/ui/')) {
          uiPatches.push(jsonPatch);
        } else if (jsonPatch.path.startsWith('/workbench/')) {
          workbenchPatches.push(jsonPatch);
        } else {
          studyPatches.push(jsonPatch);
        }
      }
      if (workbenchPatches.length > 0) {
        this.getStudy().getWorkbench().updateWorkbenchFromPatches(workbenchPatches, uiPatches);
      }
      if (uiPatches.length > 0) {
        this.getStudy().getUi().updateUiFromPatches(uiPatches);
      }
      if (studyPatches.length > 0) {
        this.getStudy().updateStudyFromPatches(studyPatches);
      }

      this.__blockUpdates = false;
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
          osparc.FlashMessenger.logError(this.tr(text), null, flashMessageDisplayDuration);
        }, this);
      }
    },

    __listenToServiceCustomEvents: function() {
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
              osparc.FlashMessenger.logAs(text, "INFO");
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
      const portId = socketData["port_key"];
      const workbench = this.getStudy().getWorkbench();
      const node = workbench.getNode(nodeId);
      if (!node) {
        if (osparc.data.Permissions.getInstance().isTester()) {
          console.log("Ignored ws 'stateInputPorts' msg", socketData);
        }
        return;
      }

      const input = node.getInput(portId);
      if (msgName === "stateInputPorts" && input) {
        const status = socketData["status"];
        input.setStatus(status);
      }

      const output = node.getOutput(portId);
      if (msgName === "stateOutputPorts" && output) {
        const status = socketData["status"];
        output.setStatus(status);
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
      if (["app", "guided"].includes(this.getStudy().getUi().getMode())) {
        // if the user is in "app" mode, return
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

      this.updateStudyDocument()
        .then(() => {
          this.__requestStartPipeline(this.getStudy().getUuid(), partialPipeline);
        })
        .catch(() => {
          this.getStudyLogger().error(null, "Run failed");
        });
    },

    __requestStartPipeline: function(studyId, partialPipeline = [], forceRestart = false) {
      this.getStudy().setPipelineRunning(true);

      if (partialPipeline.length) {
        this.getStudyLogger().info(null, "Starting partial pipeline");
      } else {
        this.getStudyLogger().info(null, "Starting pipeline");
      }

      const params = {
        url: {
          "studyId": studyId
        },
        data: {
          "subgraph": partialPipeline,
          "force_restart": forceRestart,
        }
      };
      osparc.data.Resources.fetch("runPipeline", "startPipeline", params)
        .then(resp => this.__onPipelineSubmitted(resp))
        .catch(err => {
          const errStatus = err.status;
          if (errStatus == "409") {
            osparc.FlashMessenger.logError(err);
            const msg = osparc.FlashMessenger.extractMessage(err);
            this.getStudyLogger().error(null, msg);
          } else if (errStatus == "422") {
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
          } else {
            osparc.FlashMessenger.logError(err);
            this.getStudyLogger().error(null, "Unsuccessful pipeline submission");
          }
          this.getStudy().setPipelineRunning(false);
        });

      return true;
    },

    __onPipelineSubmitted: function(response) {
      const pipelineId = response["pipeline_id"];
      const iterationRefIds = response["ref_ids"];
      this.getStudyLogger().debug(null, "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.getStudyLogger().error(null, "Submission failed");
      } else {
        if (iterationRefIds) {
          this.__reloadSnapshotsAndIterations();
        }
        this.getStudyLogger().info(null, "Pipeline started");
      }
    },

    __stopPipeline: function() {
      if (!osparc.data.Permissions.getInstance().canDo("study.stop", true)) {
        return;
      }

      this.__requestStopPipeline();
    },

    __requestStopPipeline: function() {
      this.getStudyLogger().info(null, "Stopping pipeline");

      const params = {
        url: {
          "studyId": this.getStudy().getUuid()
        },
      };
      osparc.data.Resources.fetch("runPipeline", "stopPipeline", params)
        .then(() => this.getStudyLogger().debug(null, "Stopping pipeline"), this)
        .catch(() => this.getStudyLogger().error(null, "Error stopping pipeline"), this);
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

    __uiModeChanged: function(newUIMode, oldUIMode) {
      switch (newUIMode) {
        case "guided":
        case "app":
          this.__viewsStack.setSelection([this.__slideshowView]);
          this.__slideshowView.startSlides();
          break;
        case "standalone":
          this.__viewsStack.setSelection([this.__workbenchView]);
          this.__workbenchView.openFirstNode();
          break;
        case "pipeline":
          this.__viewsStack.setSelection([this.__workbenchView]);
          this.__workbenchView.setMaximized(false);
          this.__workbenchView.showPipeline();
          break;
        case "workbench":
        default: {
          this.__viewsStack.setSelection([this.__workbenchView]);
          // OM: Is this needed?
          if (oldUIMode === "standalone") {
            // in this transition, show workbenchUI
            this.__workbenchView.setMaximized(false);
            // uncomment this when we release the osparc<->s4l integration
            // this.__workbenchView.showPipeline();
          } else {
            const currentNodeId = this.getStudy().getUi().getCurrentNodeId();
            if (currentNodeId && this.getStudy().getWorkbench().getNode(currentNodeId)) {
              const node = this.getStudy().getWorkbench().getNode(currentNodeId);
              if (node && node.isDynamic()) {
                this.__workbenchView.fullscreenNode(currentNodeId);
              } else {
                this.__workbenchView.nodeSelected(currentNodeId);
              }
            } else {
              this.__workbenchView.openFirstNode();
            }
          }
          break;
        }
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
          .catch(err => osparc.FlashMessenger.logError(err));

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

    // ------------------ IDLING TRACKER ------------------
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
    // ------------------ IDLING TRACKER ------------------

    __stopTimers: function() {
      this.__stopIdlingTracker();
    },

    __getStudyDiffs: function() {
      const sourceStudy = this.getStudy().serialize();
      const studyDiffs = {
        sourceStudy,
        delta: {},
      }
      const delta = this.__calculateDelta(this.__lastSyncedProjectDocument, sourceStudy);
      if (delta) {
        studyDiffs.delta = delta;
      }
      return studyDiffs;
    },

    __calculateDelta: function(studyA, studyB) {
      const delta = osparc.wrapper.JsonDiffPatch.getInstance().diff(studyA, studyB);
       // curate delta
      if (delta) {
        delete delta["prjOwner"];
        // lastChangeDate and creationDate should not be taken into account as data change
        delete delta["creationDate"];
        delete delta["lastChangeDate"];
        // Handle edge case: empty string vs null is not a real change
        ["thumbnail", "description"].forEach(prop => {
          if (
            prop in delta &&
            Object.keys(delta[prop]).length === 2 &&
            (delta[prop][0] === "" || delta[prop][0] === null) &&
            (delta[prop][1] === "" || delta[prop][1] === null)
          ) {
            delete delta[prop];
          }
        });
      }
      return delta;
    },

    // didStudyChange takes around 0.5ms
    didStudyChange: function() {
      const studyDiffs = this.__getStudyDiffs();
      const changed = Boolean(Object.keys(studyDiffs.delta).length);
      this.getStudy().setSavePending(changed);
      return changed;
    },

    /**
     * @param {JSON Patch} data It will soon be used to patch the project document https://datatracker.ietf.org/doc/html/rfc6902
     */
    __projectDocumentChanged: function(patchData) {
      patchData["userGroupId"] = osparc.auth.Data.getInstance().getGroupId();
      // avoid echo loop
      if (this.__blockUpdates) {
        return;
      }

      this.getStudy().setSavePending(true);
      // throttling: do not update study document right after a change, wait for THROTTLE_PATCH_TIME
      if (!this.__throttledPatchPending) {
        this.__throttledPatchPending = true;

        setTimeout(() => {
          this.updateStudyDocument();
          this.__throttledPatchPending = false;
        }, this.self().THROTTLE_PATCH_TIME);
      }
    },

    updateStudyDocument: function() {
      if (!osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights())) {
        return new Promise(resolve => {
          resolve();
        });
      }

      this.getStudy().setSavePending(true);
      this.__updatingStudy++;
      const studyDiffs = this.__getStudyDiffs();
      return this.getStudy().patchStudyDiffs(studyDiffs.delta, studyDiffs.sourceStudy)
        .then(studyData => this.__setLastSyncedProjectDocument(studyData))
        .catch(error => {
          if ("status" in error && error.status === 409) {
            console.log("Flash message blocked"); // Workaround for osparc-issues #1189
          } else {
            osparc.FlashMessenger.logError(this.tr("Error saving the study"));
          }
          this.getStudyLogger().error(null, "Error updating pipeline");
          // Need to throw the error to be able to handle it later
          throw error;
        })
        .finally(() => {
          this.getStudy().setSavePending(false);
          this.__updatingStudy--;
          if (this.__updateThrottled && this.__updatingStudy === 0) {
            this.__updateThrottled = false;
            this.updateStudyDocument();
          }
        });
    },

    __closeStudy: function() {
      osparc.store.Study.getInstance().closeStudy(this.getStudy().getUuid())
        .catch(err => console.error(err));
    },

    closeEditor: function() {
      this.__stopTimers();
      if (this.getStudy()) {
        this.getStudy().stopStudy();
        this.__closeStudy();
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
