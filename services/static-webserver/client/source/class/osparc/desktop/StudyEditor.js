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

    this._setLayout(new qx.ui.layout.VBox(10));

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

    workbenchView.addListener("slidesEdit", () => this.fireEvent("slidesEdit"), this);
    workbenchView.addListener("slidesAppStart", () => this.fireEvent("slidesAppStart"), this);
    slideshowView.addListener("slidesStop", () => this.fireEvent("slidesStop"));

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


    this._add(viewsStack, {
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
    "slidesEdit": "qx.event.type.Event",
    "slidesAppStart": "qx.event.type.Event",
    "slidesStop": "qx.event.type.Event",
    "startSnapshot": "qx.event.type.Data",
    "startIteration": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    },

    pageContext: {
      check: ["workbench", "guided", "app"],
      nullable: false,
      event: "changePageContext",
      apply: "_applyPageContext"
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
    __lastSavedStudy: null,
    __updatingStudy: null,
    __updateThrottled: null,
    __nodesSlidesTree: null,

    setStudyData: function(studyData) {
      return new Promise((resolve, reject) => {
        if (this.__settingStudy) {
          resolve();
          return;
        }
        this.__settingStudy = true;

        this._showLoadingPage(this.tr("Starting ") + (studyData.name || osparc.product.Utils.getStudyAlias({firstUpperCase: true})));

        // Before starting a study, make sure the latest version is fetched
        const params = {
          url: {
            "studyId": studyData.uuid
          }
        };
        const promises = [
          osparc.data.Resources.getOne("studies", params),
          osparc.store.Store.getInstance().getAllServices()
        ];
        Promise.all(promises)
          .then(values => {
            studyData = values[0];
            const study = new osparc.data.model.Study(studyData);
            this.setStudy(study);
            resolve();
          });
      });
    },

    _applyStudy: function(study) {
      this.__settingStudy = false;

      this._showLoadingPage(this.tr("Opening ") + (study.getName() || osparc.product.Utils.getStudyAlias({firstUpperCase: true})));

      const store = osparc.store.Store.getInstance();
      store.setCurrentStudy(study);

      this.__reloadSnapshotsAndIterations();

      study.openStudy()
        .then(() => {
          this.__lastSavedStudy = study.serialize();

          this.__workbenchView.setStudy(study);
          this.__slideshowView.setStudy(study);

          study.initStudy();

          if (osparc.product.Utils.isProduct("s4llite")) {
            this.__startIdlingTracker();
          }

          // Count dynamic services.
          // If it is larger than PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES, dynamics won't start -> Flash Message
          const maxNumber = osparc.store.StaticInfo.getInstance().getMaxNumberDyNodes();
          if (maxNumber) {
            const nodes = study.getWorkbench().getNodes();
            const nDynamics = Object.values(nodes).filter(node => node.isDynamic()).length;
            if (nDynamics > maxNumber) {
              let msg = this.tr("The Study contains more than ") + maxNumber + this.tr(" Interactive services.");
              msg += "<br>";
              msg += this.tr("Please start them manually.");
              osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
            }
          }

          osparc.data.Resources.get("organizations")
            .then(() => {
              if (osparc.data.model.Study.canIWrite(study.getAccessRights())) {
                this.__startAutoSaveTimer();
              } else {
                const msg = this.self().READ_ONLY_TEXT;
                osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
              }
            });

          const pageContext = this.isPropertyInitialized("pageContext") ? this.getPageContext() : null;
          switch (pageContext) {
            case "guided":
            case "app":
              this.__slideshowView.startSlides();
              break;
            default:
              this.__workbenchView.openFirstNode();
              break;
          }
          // the property might not be yet initialized
          if (this.isPropertyInitialized("pageContext")) {
            this.bind("pageContext", study.getUi(), "mode");
          } else {
            this.addListener("changePageContext", e => {
              const pageCxt = e.getData();
              study.getUi().setMode(pageCxt);
            });
          }

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
        })
        .catch(err => {
          let msg = "";
          if ("status" in err && err["status"] == 409) { // max_open_studies_per_user
            msg = err["message"];
          } else if ("status" in err && err["status"] == 423) { // Locked
            msg = study.getName() + this.tr(" is already opened");
          } else {
            console.error(err);
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

    editSlides: function() {
      if (this.getPageContext() !== "workbench") {
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
      this.updateStudyDocument(true)
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
      req.addListener("fail", e => {
        if (e.getTarget().getStatus() == "403") {
          this.getStudyLogger().error(null, "Pipeline is already running");
        } else if (e.getTarget().getStatus() == "422") {
          this.getStudyLogger().info(null, "The pipeline is up-to-date");
          const msg = this.tr("The pipeline is up-to-date. Do you want to re-run it?");
          const win = new osparc.ui.window.Confirmation(msg).set({
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
        socket.getSocket().once("projectStateUpdated", jsonStr => {
          const study = JSON.parse(jsonStr);
          if (study["project_uuid"] === pipelineId) {
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
      this.updateStudyDocument(false)
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

    // overridden
    _showMainLayout: function(show) {
      this.__viewsStack.setVisibility(show ? "visible" : "excluded");
    },

    nodeSelected: function(nodeId) {
      this.__workbenchView.nodeSelected(nodeId);
      this.__slideshowView.nodeSelected(nodeId);
    },

    getStudyLogger: function() {
      return this.__workbenchView.getLogger();
    },

    _applyPageContext: function(newCtxt) {
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
          this.__slideshowView.startSlides();
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
        iterations.unlistenToNodeUpdates();
        this.__workbenchView.listenToNodeUpdated();
      }, this);
    },

    __startIdlingTracker: function() {
      if (this.__studyEditorIdlingTracker) {
        this.__studyEditorIdlingTracker.stop();
        this.__studyEditorIdlingTracker = null;
      }
      const studyEditorIdlingTracker = this.__studyEditorIdlingTracker = new osparc.desktop.StudyEditorIdlingTracker();
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
      let timer = this.__autoSaveTimer = new qx.event.Timer(this.self().AUTO_SAVE_INTERVAL);
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

    __stopTimers: function() {
      this.__stopIdlingTracker();
      this.__stopAutoSaveTimer();
    },

    didStudyChange: function() {
      const newObj = this.getStudy().serialize();
      const diffPatcher = osparc.wrapper.JsonDiffPatch.getInstance();
      const delta = diffPatcher.diff(this.__lastSavedStudy, newObj);
      if (delta) {
        let deltaKeys = Object.keys(delta);
        // lastChangeDate and creationDate should not be taken into account as data change
        [
          "creationDate",
          "lastChangeDate"
        ].forEach(prop => {
          const index = deltaKeys.indexOf(prop);
          if (index > -1) {
            deltaKeys.splice(index, 1);
          }
        });

        return deltaKeys.length;
      }
      return false;
    },

    __checkStudyChanges: function() {
      if (this.didStudyChange()) {
        if (this.__updatingStudy > 0) {
          // throttle update
          this.__updateThrottled = true;
        } else {
          this.updateStudyDocument(false);
        }
      }
    },

    updateStudyDocument: function(run = false) {
      if (!osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights())) {
        return new Promise(resolve => {
          resolve();
        });
      }

      this.__updatingStudy++;
      const newObj = this.getStudy().serialize();
      return this.getStudy().updateStudy(newObj, run)
        .then(() => {
          this.__lastSavedStudy = osparc.wrapper.JsonDiffPatch.getInstance().clone(newObj);
        })
        .catch(error => {
          if ("status" in error && error.status === 409) {
            osparc.FlashMessenger.getInstance().logAs(error.message, "ERROR");
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
            this.updateStudyDocument(false);
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
      osparc.data.Resources.fetch("studies", "close", params);
    },

    closeEditor: function() {
      this.__stopTimers();
      if (this.getStudy()) {
        this.getStudy().stopStudy();
        this.__closeStudy();
      }
      const clusterMiniView = this.__workbenchView.getStartStopButtons().getClusterMiniView();
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
