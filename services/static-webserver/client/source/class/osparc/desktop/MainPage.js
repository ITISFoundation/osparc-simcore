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
 *     - TemplateBrowser
 *     - ServiceBrowser
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
    navBar.addListener("downloadStudyLogs", () => this.__downloadStudyLogs(), this);
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
    Promise.all(preloadPromises)
      .then(() => {
        const mainStack = this.__createMainStack();
        this._add(mainStack, {
          flex: 1
        });

        this.__listenToWalletSocket();
        this.__attachHandlers();
      });
  },

  members: {
    __navBar: null,
    __dashboard: null,
    __loadingPage: null,
    __studyEditor: null,

    __listenToWalletSocket: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (!socket.slotExists("walletOsparcCreditsUpdated")) {
        socket.on("walletOsparcCreditsUpdated", data => {
          const store = osparc.store.Store.getInstance();
          const walletFound = store.getWallets().find(wallet => wallet.getWalletId() === parseInt(data["wallet_id"]));
          if (walletFound) {
            walletFound.setCreditsAvailable(parseFloat(data["osparc_credits"]));
          }
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
          const win = new osparc.ui.window.Confirmation();
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
      // reset templates
      this.__dashboard.getTemplateBrowser().invalidateTemplates();
      this.__dashboard.getTemplateBrowser().reloadResources();
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

    __downloadStudyLogs: function() {
      if (this.__studyEditor) {
        this.__studyEditor.getStudyLogger().downloadLogs();
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
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const params = {
        url: {
          "study_id": data["studyData"].uuid,
          "copy_data": data["copyData"]
        },
        data: data["studyData"]
      };
      const options = {
        pollTask: true
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "postToTemplate", params, options);
      const pollTasks = osparc.data.PollTasks.getInstance();
      const interval = 1000;
      pollTasks.createPollingTask(fetchPromise, interval)
        .then(task => {
          const templateBrowser = this.__dashboard.getTemplateBrowser();
          if (templateBrowser) {
            templateBrowser.taskToTemplateReceived(task, data["studyData"].name);
          }
          task.addListener("resultReceived", e => {
            const templateData = e.getData();
            osparc.info.StudyUtils.addCollaborators(templateData, data["accessRights"]);
          });
        })
        .catch(errMsg => {
          const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
          osparc.FlashMessenger.logAs(msg, "ERROR");
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
            const msg = this.tr("Snapshot not found");
            throw new Error(msg);
          }
          const params2 = {
            url: {
              "studyId": studyId
            }
          };
          osparc.data.Resources.getOne("studies", params2)
            .then(studyData => {
              if (!studyData) {
                const msg = this.tr("Study not found");
                throw new Error(msg);
              }
              osparc.desktop.MainPageHandler.getInstance().loadStudy(studyData);
            });
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
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
      const params = {
        url: {
          "studyId": iterationUuid
        }
      };
      // OM TODO. DO NOT ADD ITERATIONS TO STUDIES CACHE
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          if (!studyData) {
            const msg = this.tr("Iteration not found");
            throw new Error(msg);
          }
          osparc.desktop.MainPageHandler.getInstance().loadStudy(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
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
