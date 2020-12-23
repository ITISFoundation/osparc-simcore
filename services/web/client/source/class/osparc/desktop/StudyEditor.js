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

    this._add(viewsStack, {
      flex: 1
    });
  },

  events: {
    "studyIsLocked": "qx.event.type.Event",
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
          const myGrpId = osparc.auth.Data.getInstance().getGroupId();
          if (osparc.component.export.StudyPermissions.canGroupWrite(study.getAccessRights(), myGrpId)) {
            this.__startAutoSaveTimer();
          } else {
            const msg = this.tr("You do not have writing permissions.<br>Changes will not be saved");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
          }
          switch (this.getPageContext()) {
            case "slideshow":
              this.__slideshowView.startSlides();
              break;
            default:
              this.__workbenchView.openFirstNode();
              break;
          }
        })
        .catch(err => {
          if ("status" in err && err["status"] == 423) { // Locked
            const msg = study.getName() + this.tr(" is already opened");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
            this.fireEvent("studyIsLocked");
          } else {
            console.error(err);
          }
        });

      this.__workbenchView.setStudy(study);
      this.__slideshowView.setStudy(study);
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

    getLogger: function() {
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
      let diffPatcher = osparc.wrapper.JsonDiffPatch.getInstance();
      // Save every 5 seconds
      const interval = 5000;
      let timer = this.__autoSaveTimer = new qx.event.Timer(interval);
      timer.addListener("interval", () => {
        const newObj = this.getStudy().serialize();
        const delta = diffPatcher.diff(this.__lastSavedStudy, newObj);
        if (delta) {
          let deltaKeys = Object.keys(delta);
          // lastChangeDate should not be taken into account as data change
          const index = deltaKeys.indexOf("lastChangeDate");
          if (index > -1) {
            deltaKeys.splice(index, 1);
          }
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
      if (!osparc.component.export.StudyPermissions.canGroupWrite(this.getStudy().getAccessRights(), myGrpId)) {
        return new Promise(resolve => {
          resolve();
        });
      }

      this.getStudy().setLastChangeDate(new Date());
      const newObj = this.getStudy().serialize();
      const prjUuid = this.getStudy().getUuid();

      const params = {
        url: {
          projectId: prjUuid,
          run
        },
        data: newObj
      };
      return osparc.data.Resources.fetch("studies", "put", params)
        .then(data => {
          this.__lastSavedStudy = osparc.wrapper.JsonDiffPatch.getInstance().clone(newObj);
        }).catch(error => {
          console.error(error);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Error saving the study"), "ERROR");
          this.getLogger().error(null, "Error updating pipeline");
          // Need to throw the error to be able to handle it later
          throw error;
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
