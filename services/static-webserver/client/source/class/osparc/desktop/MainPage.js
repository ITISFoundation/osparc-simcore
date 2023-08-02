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
    this.base();

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this._add(osparc.component.notification.RibbonNotifications.getInstance());

    const navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    // Some resources request before building the main stack
    osparc.WindowSizeTracker.getInstance().startTracker();
    osparc.MaintenanceTracker.getInstance().startTracker();

    osparc.data.Resources.dummy.addWalletsToStore();
    // osparc.data.Resources.addWalletsToStore();

    const store = osparc.store.Store.getInstance();

    Promise.all([
      store.getAllClassifiers(true),
      store.getTags()
    ]).then(() => {
      const mainStack = this.__createMainStack();
      this._add(mainStack, {
        flex: 1
      });

      this.__attachHandlers();
    });
  },

  statics: {
    MIN_STUDIES_PER_ROW: 4
  },

  members: {
    __navBar: null,
    __dashboard: null,
    __dashboardLayout: null,
    __loadingPage: null,
    __studyEditor: null,

    __createNavigationBar: function() {
      const navBar = new osparc.navigation.NavigationBar();
      navBar.addListener("backToDashboardPressed", () => this.__backToDashboardPressed(), this);
      navBar.addListener("downloadStudyLogs", () => this.__downloadStudyLogs(), this);
      return navBar;
    },

    __backToDashboardPressed: function() {
      if (!osparc.data.Permissions.getInstance().canDo("studies.user.create", true)) {
        return;
      }
      if (this.__studyEditor) {
        const isReadOnly = this.__studyEditor.getStudy().isReadOnly();
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (!isReadOnly && preferencesSettings.getConfirmBackToDashboard()) {
          const studyName = this.__studyEditor.getStudy().getName();
          const win = new osparc.ui.window.Confirmation();
          if (osparc.product.Utils.isProduct("s4l") || osparc.product.Utils.isProduct("s4llite")) {
            let msg = this.tr("Do you want to close ") + "<b>" + studyName + "</b>?";
            msg += "<br><br>";
            msg += this.tr("Make sure you saved your changes to:");
            msg += "<br>";
            msg += this.tr("- current <b>smash file</b> (running <b>simulations</b>, if any, will be terminated)");
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
        await this.__studyEditor.updateStudyDocument(false);
      }
      this.closeEditor();
      this.__showDashboard();
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

      const dashboardLayout = this.__dashboardLayout = this.__createDashboardStack();
      mainPageHandler.addDashboard(dashboardLayout);

      const loadingPage = this.__loadingPage = new osparc.ui.message.Loading();
      mainPageHandler.addLoadingPage(loadingPage);

      const studyEditor = this.__studyEditor = this.__getStudyEditor();
      mainPageHandler.addStudyEditor(studyEditor);

      mainPageHandler.addListener("syncStudyEditor", e => this.__syncStudyEditor(e.getData()));

      return mainStack;
    },

    __createDashboardStack: function() {
      const dashboard = this.__dashboard = new osparc.dashboard.Dashboard();
      const tabsBar = dashboard.getChildControl("bar");
      tabsBar.set({
        paddingBottom: 6
      });
      this.__navBar.addDashboardTabButtons(tabsBar);
      const itemWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING;
      dashboard.setMinWidth(this.self().MIN_STUDIES_PER_ROW * itemWidth + 8);
      const fitResourceCards = () => {
        const w = document.documentElement.clientWidth;
        const nStudies = Math.floor((w - 2*150 - 8) / itemWidth);
        const newWidth = nStudies * itemWidth + 8;
        if (newWidth > dashboard.getMinWidth()) {
          dashboard.setWidth(newWidth);
        } else {
          dashboard.setWidth(dashboard.getMinWidth());
        }
      };
      fitResourceCards();
      window.addEventListener("resize", () => fitResourceCards());
      const dashboardLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      dashboardLayout.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      dashboardLayout.add(dashboard);
      dashboardLayout.add(new qx.ui.core.Widget(), {
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
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const params = {
        url: {
          "study_id": data["studyData"].uuid,
          "copy_data": data["copyData"]
        },
        data: data["studyData"]
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "postToTemplate", params, null, {"pollTask": true});
      const pollTasks = osparc.data.PollTasks.getInstance();
      const interval = 1000;
      pollTasks.createPollingTask(fetchPromise, interval)
        .then(task => {
          const templateBrowser = this.__dashboard.getTemplateBrowser();
          if (templateBrowser) {
            templateBrowser.taskToTemplateReceived(task, data["studyData"].name);
          }
        })
        .catch(errMsg => {
          const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __showDashboard: function() {
      if (!osparc.data.Permissions.getInstance().canDo("dashboard.read")) {
        // If guest fails to load study, log him out
        osparc.auth.Manager.getInstance().logout();
        return;
      }

      osparc.desktop.MainPageHandler.getInstance().showDashboard();
      this.__navBar.show();
      this.__navBar.setStudy(null);
      this.__navBar.setPageContext("dashboard");
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

    __showStudyEditor: function(studyEditor) {
      osparc.desktop.MainPageHandler.getInstance().replaceStudyEditor(studyEditor);
      osparc.desktop.MainPageHandler.getInstance().showStudyEditor();
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
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
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
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.__showDashboard();
          return;
        });
    },

    closeStudy: function(studyId) {
      if (studyId === undefined) {
        if (this.__studyEditor && this.__studyEditor.getStudy()) {
          studyId = this.__studyEditor.getStudy().getUuid();
        } else {
          return;
        }
      }
      const params = {
        url: {
          "studyId": studyId
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      osparc.data.Resources.fetch("studies", "close", params);
    },

    __syncStudyEditor: function(pageContext = "workbench") {
      const studyEditor = this.__studyEditor;
      const study = studyEditor.getStudy();
      this.__navBar.setStudy(study);
      this.__navBar.setPageContext(pageContext);
      studyEditor.setPageContext(pageContext);
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
      studyEditor.addListener("slidesEdit", () => {
        studyEditor.editSlides();
      }, this);
      studyEditor.addListener("slidesAppStart", () => {
        this.__navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
        studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
      }, this);
      studyEditor.addListener("slidesStop", () => {
        this.__navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
        this.__studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
      }, this);
      return studyEditor;
    }
  }
});
