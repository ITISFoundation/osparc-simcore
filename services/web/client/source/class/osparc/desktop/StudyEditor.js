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
    workbenchView.addListener("startStudy", e => {
      this.fireDataEvent("startStudy", e.getData());
    });
    viewsStack.add(workbenchView);

    const slideshowView = this.__slideshowView = new osparc.desktop.SlideShowView();
    viewsStack.add(slideshowView);

    slideshowView.addListener("startPartialPipeline", e => {
      const partialPipeline = e.getData();
      this.__startPipeline(partialPipeline);
    }, this);

    [
      workbenchView.getStartStopButtons(),
      slideshowView.getStartStopButtons()
    ].forEach(startStopButtons => {
      startStopButtons.addListener("startPipeline", () => {
        this.__startPipeline([]);
      }, this);
      startStopButtons.addListener("startPartialPipeline", () => {
        const partialPipeline = this.getPageContext() === "workbench" ? this.__workbenchView.getSelectedNodeIDs() : this.__slideshowView.getSelectedNodeIDs();
        this.__startPipeline(partialPipeline);
      }, this);
      startStopButtons.addListener("stopPipeline", this.__stopPipeline, this);
    });

    this._add(viewsStack, {
      flex: 1
    });
  },

  events: {
    "forceBackToDashboard": "qx.event.type.Event",
    "startStudy": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    },

    pageContext: {
      check: ["workbench", "slideshow"],
      nullable: false,
      apply: "_applyPageContext"
    }
  },

  members: {
    __study: null,
    __settingStudy: null,
    __viewsStack: null,
    __workbenchView: null,
    __slideshowView: null,
    __autoSaveTimer: null,
    __lastSavedStudy: null,

    setStudyData: function(studyData) {
      return new Promise((resolve, reject) => {
        if (this.__settingStudy) {
          resolve();
          return;
        }
        this.__settingStudy = true;

        this._showLoadingPage(this.tr("Starting ") + (studyData.name || this.tr("Study")));

        // Before starting a study, make sure the latest version is fetched
        const params = {
          url: {
            "projectId": studyData.uuid
          }
        };
        const promises = [
          osparc.data.Resources.getOne("studies", params),
          osparc.store.Store.getInstance().getServicesDAGs()
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

      this._hideLoadingPage();

      osparc.store.Store.getInstance().setCurrentStudy(study);
      study.buildWorkbench();
      study.openStudy()
        .then(() => {
          study.initStudy();

          osparc.data.Resources.get("organizations")
            .then(resp => {
              const myGroupId = osparc.auth.Data.getInstance().getGroupId();
              const orgs = resp["organizations"];
              const orgIDs = [myGroupId];
              orgs.forEach(org => orgIDs.push(org["gid"]));

              if (osparc.component.permissions.Study.canGroupsWrite(study.getAccessRights(), orgIDs)) {
                this.__startAutoSaveTimer();
              } else {
                const msg = this.tr("You do not have writing permissions.<br>Changes will not be saved");
                osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
              }
            });

          switch (this.getPageContext()) {
            case "slideshow":
              this.__slideshowView.startSlides();
              break;
            default:
              this.__workbenchView.openFirstNode();
              break;
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

          const socket = osparc.wrapper.WebSocket.getInstance();
          socket.addListener("connect", () => {
            const params = {
              url: {
                tabId: osparc.utils.Utils.getClientSessionID()
              }
            };
            osparc.data.Resources.fetch("studies", "getActive", params)
              .then(studyData => {
                if (studyData === null) {
                  this.__noLongerActive();
                }
              })
              .catch(() => this.__noLongerActive());
          });
        })
        .catch(err => {
          if ("status" in err && err["status"] == 423) { // Locked
            const msg = study.getName() + this.tr(" is already opened");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
            this.fireEvent("forceBackToDashboard");
          } else {
            console.error(err);
          }
        });

      this.__workbenchView.setStudy(study);
      this.__slideshowView.setStudy(study);
    },

    __noLongerActive: function() {
      // This might happen when the socket connection is lost and the study gets closed
      const msg = this.tr("Study was closed while you were offline");
      osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      this.fireEvent("forceBackToDashboard");
    },


    // ------------------ START/STOP PIPELINE ------------------
    __startPipeline: function(partialPipeline = []) {
      if (!osparc.data.Permissions.getInstance().canDo("study.start", true)) {
        return;
      }

      const startStopButtonsWB = this.__workbenchView.getStartStopButtons();
      const startStopButtonsSS = this.__slideshowView.getStartStopButtons();
      startStopButtonsWB.setRunning(true);
      startStopButtonsSS.setRunning(true);
      this.updateStudyDocument(true)
        .then(() => {
          this.__doStartPipeline(partialPipeline);
        })
        .catch(() => {
          this.__getStudyLogger().error(null, "Run failed");
          startStopButtonsWB.setRunning(false);
          startStopButtonsSS.setRunning(false);
        });
    },

    __doStartPipeline: function(partialPipeline) {
      if (this.getStudy().getSweeper().hasSecondaryStudies()) {
        const secondaryStudyIds = this.getStudy().getSweeper().getSecondaryStudyIds();
        secondaryStudyIds.forEach(secondaryStudyId => {
          this.__requestStartPipeline(secondaryStudyId);
        });
      } else {
        this.__requestStartPipeline(this.getStudy().getUuid(), partialPipeline);
      }
    },

    __requestStartPipeline: function(studyId, partialPipeline = [], forceRestart = false) {
      const url = "/computation/pipeline/" + encodeURIComponent(studyId) + ":start";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      const startStopButtonsWB = this.__workbenchView.getStartStopButtons();
      const startStopButtonsSS = this.__slideshowView.getStartStopButtons();
      req.addListener("success", this.__onPipelinesubmitted, this);
      req.addListener("error", e => {
        this.__getStudyLogger().error(null, "Error submitting pipeline");
        startStopButtonsWB.setRunning(false);
        startStopButtonsSS.setRunning(false);
      }, this);
      req.addListener("fail", e => {
        if (e.getTarget().getStatus() == "403") {
          this.__getStudyLogger().error(null, "Pipeline is already running");
        } else if (e.getTarget().getStatus() == "422") {
          this.__getStudyLogger().info(null, "The pipeline is up-to-date");
          const msg = this.tr("The pipeline is up-to-date. Do you want to re-run it?");
          const win = new osparc.ui.window.Confirmation(msg);
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__requestStartPipeline(studyId, partialPipeline, true);
            }
          }, this);
        } else {
          this.__getStudyLogger().error(null, "Failed submitting pipeline");
        }
        startStopButtonsWB.setRunning(false);
        startStopButtonsSS.setRunning(false);
      }, this);

      req.setRequestData({
        "subgraph": partialPipeline,
        "force_restart": forceRestart
      });
      req.send();
      if (partialPipeline.length) {
        this.__getStudyLogger().info(null, "Starting partial pipeline");
      } else {
        this.__getStudyLogger().info(null, "Starting pipeline");
      }

      return true;
    },

    __onPipelinesubmitted: function(e) {
      const resp = e.getTarget().getResponse();
      const pipelineId = resp.data["pipeline_id"];
      this.__getStudyLogger().debug(null, "Pipeline ID " + pipelineId);
      const notGood = [null, undefined, -1];
      if (notGood.includes(pipelineId)) {
        this.__getStudyLogger().error(null, "Submission failed");
      } else {
        this.__getStudyLogger().info(null, "Pipeline started");
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

      this.__doStopPipeline();
    },

    __doStopPipeline: function() {
      if (this.getStudy().getSweeper().hasSecondaryStudies()) {
        const secondaryStudyIds = this.getStudy().getSweeper().getSecondaryStudyIds();
        secondaryStudyIds.forEach(secondaryStudyId => {
          this.__requestStopPipeline(secondaryStudyId);
        });
      } else {
        this.__requestStopPipeline(this.getStudy().getUuid());
      }
    },

    __requestStopPipeline: function(studyId) {
      const url = "/computation/pipeline/" + encodeURIComponent(studyId) + ":stop";
      const req = new osparc.io.request.ApiRequest(url, "POST");
      req.addListener("success", e => {
        this.__getStudyLogger().debug(null, "Pipeline aborting");
      }, this);
      req.addListener("error", e => {
        this.__getStudyLogger().error(null, "Error stopping pipeline");
      }, this);
      req.addListener("fail", e => {
        this.__getStudyLogger().error(null, "Failed stopping pipeline");
      }, this);
      req.send();

      this.__getStudyLogger().info(null, "Stopping pipeline");
      return true;
    },
    // ------------------ START/STOP PIPELINE ------------------

    __updatePipelineAndRetrieve: function(node, portKey = null) {
      this.updateStudyDocument(false)
        .then(() => {
          this.__getStudyLogger().debug(null, "Retrieveing inputs");
          if (node) {
            node.retrieveInputs(portKey);
          }
        });
      this.__getStudyLogger().debug(null, "Updating pipeline");
    },

    // overridden
    _showMainLayout: function(show) {
      this.__viewsStack.setVisibility(show ? "visible" : "excluded");
    },

    /**
     * Destructor
     */
    destruct: function() {
      osparc.store.Store.getInstance().setCurrentStudy(null);
      this.__stopAutoSaveTimer();
    },

    nodeSelected: function(nodeId) {
      this.__workbenchView.nodeSelected(nodeId);
      this.__slideshowView.nodeSelected(nodeId);
    },

    __getStudyLogger: function() {
      return this.__workbenchView.getLogger();
    },

    _applyPageContext: function(newCtxt) {
      switch (newCtxt) {
        case "workbench":
          this.__viewsStack.setSelection([this.__workbenchView]);
          this.__workbenchView.nodeSelected(this.getStudy().getUi().getCurrentNodeId());
          break;
        case "slideshow":
          this.__viewsStack.setSelection([this.__slideshowView]);
          this.__slideshowView.startSlides();
          break;
      }
    },

    __startAutoSaveTimer: function() {
      const diffPatcher = osparc.wrapper.JsonDiffPatch.getInstance();
      // Save every 3 seconds
      const interval = 3000;
      let timer = this.__autoSaveTimer = new qx.event.Timer(interval);
      timer.addListener("interval", () => {
        if (!osparc.wrapper.WebSocket.getInstance().isConnected()) {
          return;
        }
        const newObj = this.getStudy().serialize();
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
          if (deltaKeys.length > 0) {
            this.updateStudyDocument(false);
          }
        }
      }, this);
      timer.start();
    },

    __stopAutoSaveTimer: function() {
      if (this.__autoSaveTimer && this.__autoSaveTimer.isEnabled()) {
        this.__autoSaveTimer.stop();
        this.__autoSaveTimer.setEnabled(false);
      }
    },

    updateStudyDocument: function(run = false) {
      const myGrpId = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
      orgIDs.push(myGrpId);
      if (!osparc.component.permissions.Study.canGroupsWrite(this.getStudy().getAccessRights(), orgIDs)) {
        return new Promise(resolve => {
          resolve();
        });
      }

      const newObj = this.getStudy().serialize();
      return this.getStudy().updateStudy(newObj, run)
        .then(data => {
          this.__lastSavedStudy = osparc.wrapper.JsonDiffPatch.getInstance().clone(newObj);
        })
        .catch(error => {
          console.error(error);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Error saving the study"), "ERROR");
          this.__getStudyLogger().error(null, "Error updating pipeline");
          // Need to throw the error to be able to handle it later
          throw error;
        });
    },

    takeScreenshot: function() {
      const html2canvas = osparc.wrapper.Html2canvas.getInstance();
      const iframes = Array.from(document.getElementsByTagName("iframe"));
      const visibleIframe = iframes.find(iframe => iframe.offsetTop >= 0);
      const elem = visibleIframe === undefined ? this.getContentElement().getDomElement() : visibleIframe.contentDocument.body;
      html2canvas.takeScreenshot(elem)
        .then(screenshot => {
          const filename = "screenshot.png";
          screenshot.name = filename;
          const dataStore = osparc.store.Data.getInstance();
          dataStore.uploadScreenshot(screenshot)
            .then(link => {
              this.getStudy().setThumbnail(link);
            });
        });
    },

    closeEditor: function() {
      this.__stopAutoSaveTimer();
      if (this.getStudy()) {
        this.getStudy().stopStudy();
      }
    }
  }
});
