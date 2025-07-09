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
/**
 * @ignore(fetch)
 */

/**
 * Widget managing the layout once the user is logged in.
 *
 * It offers a:
 * - NavigationBar
 * - Main Stack
 *   - Dashboard Stack
 *     - StudyBrowser
 *     - TutorialBrowser
 *     - AppBrowser
 *     - DataManager
 *   - StudyEditor
 *
 * <pre class='javascript'>
 *   let mainPage = new osparc.desktop.MainPage();
 *   this.getRoot().add(mainPage);
 * </pre>
 */

qx.Class.define("osparc.desktop.MainPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this._add(osparc.notification.RibbonNotifications.getInstance());

    const navBar = this.__navBar = new osparc.navigation.NavigationBar();
    navBar.populateLayout();
    navBar.addListener("backToDashboardPressed", () => this.__backToDashboardPressed(), this);
    navBar.addListener("openLogger", () => this.__openLogger(), this);
    this._add(navBar);

    // Some resources request before building the main stack
    osparc.MaintenanceTracker.getInstance().startTracker();
    osparc.CookieExpirationTracker.getInstance().startTracker();
    osparc.NewUITracker.getInstance().startTracker();

    const store = osparc.store.Store.getInstance();
    const preloadPromises = [];
    const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
    if (walletsEnabled) {
      preloadPromises.push(store.reloadCreditPrice());
      preloadPromises.push(store.reloadWallets());
    }
    preloadPromises.push(store.getAllClassifiers(true));
    preloadPromises.push(osparc.store.Tags.getInstance().fetchTags());
    preloadPromises.push(osparc.store.Products.getInstance().fetchUiConfig());
    preloadPromises.push(osparc.store.PollTasks.getInstance().fetchTasks());
    preloadPromises.push(osparc.store.Jobs.getInstance().fetchJobsLatest());
    preloadPromises.push(osparc.data.Permissions.getInstance().fetchPermissions());
    preloadPromises.push(osparc.data.Permissions.getInstance().fetchFunctionPermissions());
    Promise.all(preloadPromises)
      .then(() => {
        const mainStack = this.__createMainStack();
        this._add(mainStack, {
          flex: 1
        });

        this.__attachTasks();
        this.__listenToWalletSocket();
        this.__attachHandlers();
      });
  },

  members: {
    __navBar: null,
    __dashboard: null,
    __loadingPage: null,
    __studyEditor: null,

    __attachTasks: function() {
      const pollTasks = osparc.store.PollTasks.getInstance();
      const exportDataTasks = pollTasks.getExportDataTasks();
      exportDataTasks.forEach(task => {
        osparc.task.ExportData.exportDataTaskReceived(task, false);
      });
    },

    __listenToWalletSocket: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (!socket.slotExists("walletOsparcCreditsUpdated")) {
        socket.on("walletOsparcCreditsUpdated", data => {
          osparc.desktop.credits.Utils.creditsUpdated(data["wallet_id"], data["osparc_credits"]);
        }, this);
      }
    },

    __backToDashboardPressed: function() {
      if (!osparc.data.Permissions.getInstance().canDo("studies.user.create", true)) {
        return;
      }
      if (this.__studyEditor) {
        const isReadOnly = this.__studyEditor.getStudy().isReadOnly();
        const preferencesSettings = osparc.Preferences.getInstance();
        if (!isReadOnly && preferencesSettings.getConfirmBackToDashboard()) {
          const studyName = this.__studyEditor.getStudy().getName();
          const win = new osparc.ui.window.Confirmation().set({
            confirmAction: "warning",
          });
          if (osparc.product.Utils.getProductName().includes("s4l")) {
            let msg = this.tr("Do you want to close ") + "<b>" + studyName + "</b>?";
            msg += "<br><br>";
            msg += this.tr("Make sure you saved your changes to:");
            msg += "<br>";
            msg += this.tr("- current <b>smash file</b>");
            msg += "<br>";
            msg += this.tr("- current <b>notebooks</b> (<b>jupyterlab</b> session will be terminated)");
            win.set({
              maxWidth: 460,
              caption: this.tr("Close"),
              message: msg,
              confirmText: this.tr("Yes")
            });
          } else {
            const msg = this.tr("Do you want to save and close ") + "<b>" + studyName + "</b>?";
            win.set({
              caption: this.tr("Save & Close"),
              message: msg,
              confirmText: this.tr("Yes")
            });
          }
          const confirmButton = win.getConfirmButton();
          osparc.utils.Utils.setIdToWidget(confirmButton, "confirmDashboardBtn");
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__backToDashboard();
            }
          }, this);
        } else {
          this.__backToDashboard();
        }
      } else {
        this.__showDashboard();
      }
    },

    __backToDashboard: async function() {
      const dashboardBtn = this.__navBar.getChildControl("dashboard-button");
      dashboardBtn.setFetching(true);
      if (this.__studyEditor.didStudyChange()) {
        // make sure very latest changes are saved
        await this.__studyEditor.updateStudyDocument();
      }
      this.closeEditor();
      this.__showDashboard();
      // reset studies
      this.__dashboard.getStudyBrowser().invalidateStudies();
      this.__dashboard.getStudyBrowser().reloadResources();
      this.__dashboard.getStudyBrowser().resetSelection();
      dashboardBtn.setFetching(false);

      const store = osparc.store.Store.getInstance();
      store.setActiveWallet(null);
    },

    closeEditor: function() {
      if (this.__studyEditor) {
        this.__studyEditor.closeEditor();
      }
    },

    __openLogger: function() {
      if (this.__studyEditor) {
        osparc.ui.window.Window.popUpInWindow(this.__studyEditor.getStudyLogger(), this.tr("Platform logger"), 950, 650);
      }
    },

    __createMainStack: function() {
      const mainStack = new qx.ui.container.Stack().set({
        alignX: "center"
      });

      const mainPageHandler = osparc.desktop.MainPageHandler.getInstance();
      mainPageHandler.setStack(mainStack);

      const dashboardLayout = this.__createDashboardLayout();
      mainPageHandler.addDashboard(dashboardLayout);

      const loadingPage = this.__loadingPage = new osparc.ui.message.Loading();
      mainPageHandler.addLoadingPage(loadingPage);

      const studyEditor = this.__studyEditor = this.__getStudyEditor();
      mainPageHandler.addStudyEditor(studyEditor);

      return mainStack;
    },

    __createDashboardLayout: function() {
      const dashboard = this.__dashboard = new osparc.dashboard.Dashboard();
      const tabsBar = dashboard.getChildControl("bar");
      tabsBar.set({
        paddingBottom: 6
      });
      this.__navBar.addDashboardTabButtons(tabsBar);
      const dashboardLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      dashboardLayout.add(dashboard, {
        flex: 1
      });
      return dashboardLayout;
    },

    __attachHandlers: function() {
      const studyBrowser = this.__dashboard.getStudyBrowser();
      studyBrowser.addListener("publishTemplate", e => this.__publishTemplate(e.getData()));
    },

    __publishTemplate: function(data) {
      const text = this.tr("Started template creation and added to the background tasks");
      osparc.FlashMessenger.logAs(text, "INFO");

      const studyId = data["studyData"].uuid;
      const studyName = data["studyData"].name;
      const copyData = data["copyData"];
      const templateAccessRights = data["accessRights"];
      const templateType = data["templateType"];

      const params = {
        url: {
          "study_id": studyId,
          "copy_data": copyData,
          "hidden": false,
        },
      };
      const options = {
        pollTask: true
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "postToTemplate", params, options);
      const pollTasks = osparc.store.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise)
        .then(task => {
          const tutorialBrowser = this.__dashboard.getTutorialBrowser();
          if (tutorialBrowser && templateType === osparc.data.model.StudyUI.TUTORIAL_TYPE) {
            tutorialBrowser.taskToTemplateReceived(task, studyName, templateType);
          }
          const appBrowser = this.__dashboard.getAppBrowser();
          if (appBrowser && templateType === osparc.data.model.StudyUI.HYPERTOOL_TYPE) {
            appBrowser.taskToTemplateReceived(task, studyName, templateType);
          }
          task.addListener("resultReceived", e => {
            const templateData = e.getData();
            // these operations need to be done after template creation
            osparc.store.Study.addCollaborators(templateData, templateAccessRights);
            if (templateType) {
              osparc.store.Study.patchTemplateType(templateData["uuid"], templateType)
                .then(() => {
                  if (tutorialBrowser && templateType === osparc.data.model.StudyUI.TUTORIAL_TYPE) {
                    tutorialBrowser.reloadResources(false);
                  }
                  if (appBrowser && templateType === osparc.data.model.StudyUI.HYPERTOOL_TYPE) {
                    appBrowser.reloadResources(false);
                  }
                });
            }
          });
        })
        .catch(errMsg => {
          const msg = this.tr("Something went wrong while duplicating the study<br>") + errMsg;
          osparc.FlashMessenger.logError(msg);
        });
    },

    __showDashboard: function() {
      if (!osparc.data.Permissions.getInstance().canDo("dashboard.read")) {
        // If guest fails to load study, log him out
        qx.core.Init.getApplication().logout();
        return;
      }

      osparc.desktop.MainPageHandler.getInstance().showDashboard();
      this.__navBar.show();
      this.__navBar.setStudy(null);
      this.__dashboard.getStudyBrowser().resetSelection();
      if (this.__studyEditor) {
        this.__studyEditor.destruct();
      }
    },

    __showLoadingPage: function(msg) {
      const mainPageHandler = osparc.desktop.MainPageHandler.getInstance();
      mainPageHandler.setLoadingPageHeader(msg);
      mainPageHandler.showLoadingPage();
    },

    __startSnapshot: async function(studyId, snapshotId) {
      this.__showLoadingPage(this.tr("Loading Snapshot"));

      this.__loadingPage.setMessages([
        this.tr("Closing previous snapshot...")
      ]);
      this.closeEditor();
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      while (currentStudy.isLocked()) {
        await osparc.utils.Utils.sleep(1000);
        store.getStudyState(studyId);
      }
      this.__loadingPage.setMessages([]);
      this.__openSnapshot(studyId, snapshotId);
    },

    __openSnapshot: function(studyId, snapshotId) {
      const params = {
        url: {
          "studyId": studyId,
          "snapshotId": snapshotId
        }
      };
      osparc.data.Resources.fetch("snapshots", "checkout", params)
        .then(snapshotResp => {
          if (!snapshotResp) {
            const msg = this.tr("No snapshot found");
            throw new Error(msg);
          }
          osparc.store.Study.getOne(studyId)
            .then(studyData => {
              if (!studyData) {
                const msg = this.tr("Project not found");
                throw new Error(msg);
              }
              osparc.desktop.MainPageHandler.getInstance().loadStudy(studyData);
            });
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          this.__showDashboard();
          return;
        });
    },

    __startIteration: async function(studyId, iterationUuid) {
      this.__showLoadingPage(this.tr("Loading Iteration"));

      this.__loadingPage.setMessages([
        this.tr("Closing...")
      ]);
      this.closeEditor();
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      while (currentStudy.isLocked()) {
        await osparc.utils.Utils.sleep(1000);
        store.getStudyState(studyId);
      }
      this.__loadingPage.setMessages([]);
      this.__openIteration(iterationUuid);
    },

    __openIteration: function(iterationUuid) {
      osparc.store.Study.getOne(iterationUuid)
        .then(studyData => {
          if (!studyData) {
            const msg = this.tr("Iteration not found");
            throw new Error(msg);
          }
          osparc.desktop.MainPageHandler.getInstance().loadStudy(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          this.__showDashboard();
          return;
        });
    },

    __getStudyEditor: function() {
      if (this.__studyEditor) {
        return this.__studyEditor;
      }
      const studyEditor = new osparc.desktop.StudyEditor();
      studyEditor.addListener("startSnapshot", e => {
        const snapshotId = e.getData();
        this.__startSnapshot(this.__studyEditor.getStudy().getUuid(), snapshotId);
      }, this);
      studyEditor.addListener("startIteration", e => {
        const iterationUuid = e.getData();
        this.__startIteration(this.__studyEditor.getStudy().getUuid(), iterationUuid);
      }, this);
      studyEditor.addListener("expandNavBar", () => this.__navBar.show());
      studyEditor.addListener("collapseNavBar", () => this.__navBar.exclude());
      studyEditor.addListener("backToDashboardPressed", () => this.__backToDashboardPressed(), this);
      studyEditor.addListener("forceBackToDashboard", () => this.__showDashboard(), this);
      studyEditor.addListener("userIdled", () => this.__backToDashboard(), this);
      studyEditor.addListener("changeStudy", e => {
        const study = e.getData();
        this.__navBar.setStudy(study);
      });
      return studyEditor;
    }
  }
});
