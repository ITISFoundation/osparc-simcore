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
 *     - DataManager
 *     - ExploreBrowser
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

    const navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    const mainStack = this.__mainStack = this.__createMainStack();
    this._add(mainStack, {
      flex: 1
    });

    this.__attachHandlers();
  },

  members: {
    __navBar: null,
    __mainStack: null,
    __dashboard: null,
    __dashboardLayout: null,
    __loadingPage: null,
    __studyEditor: null,

    __createNavigationBar: function() {
      const navBar = new osparc.navigation.NavigationBar();
      navBar.addListener("backToDashboardPressed", () => this.__backToDashboardPressed(), this);
      return navBar;
    },

    __backToDashboardPressed: function() {
      if (!osparc.data.Permissions.getInstance().canDo("studies.user.create", true)) {
        return;
      }
      if (this.__studyEditor) {
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (preferencesSettings.getConfirmBackToDashboard()) {
          const msg = this.tr("Do you really want to close the study?");
          const win = new osparc.ui.window.Confirmation(msg);
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

    __backToDashboard: function() {
      const dashboardBtn = this.__navBar.getChildControl("dashboard-button");
      dashboardBtn.setFetching(true);
      const studyId = this.__studyEditor.getStudy().getUuid();
      this.__studyEditor.updateStudyDocument()
        .then(() => {
          this.__studyEditor.closeEditor();
          this.__showDashboard();
          this.__dashboard.getStudyBrowser().invalidateStudies();
          this.__dashboard.getStudyBrowser().reloadStudies();
          this.__dashboard.getStudyBrowser().resetSelection();
          this.__dashboard.getStudyBrowser().reloadStudy(studyId)
            .then(() => {
              this.__closeStudy(studyId);
            });
        })
        .finally(() => {
          dashboardBtn.setFetching(false);
        });
    },

    __createMainStack: function() {
      const mainStack = new qx.ui.container.Stack().set({
        alignX: "center"
      });

      const dashboardLayout = this.__dashboardLayout = this.__createDashboardStack();
      mainStack.add(dashboardLayout);

      const loadingPage = this.__loadingPage = new osparc.ui.message.Loading();
      mainStack.add(loadingPage);

      const studyEditor = this.__studyEditor = this.__getStudyEditor();
      mainStack.add(studyEditor);

      return mainStack;
    },

    __createDashboardStack: function() {
      const dashboard = this.__dashboard = new osparc.dashboard.Dashboard();
      const minNStudyItemsPerRow = 5;
      const itemWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING;
      dashboard.setMinWidth(minNStudyItemsPerRow * itemWidth + 8);
      const sideSearch = new osparc.dashboard.SideSearch().set({
        maxWidth: 330,
        minWidth: 220
      });
      const fitResourceCards = () => {
        const w = document.documentElement.clientWidth;
        const nStudies = Math.floor((w - 2*sideSearch.getSizeHint().width - 8) / itemWidth);
        const newWidth = nStudies * itemWidth + 8;
        if (newWidth > dashboard.getMinWidth()) {
          dashboard.setWidth(newWidth);
        } else {
          dashboard.setWidth(dashboard.getMinWidth());
        }
      };
      fitResourceCards();
      window.addEventListener("resize", () => fitResourceCards());
      dashboard.bind("selection", sideSearch, "visibility", {
        converter: value => {
          const tabIndex = dashboard.getChildren().indexOf(value[0]);
          return [0, 1].includes(tabIndex) ? "visible" : "hidden";
        }
      });
      const dashboardLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      dashboardLayout.add(sideSearch, {
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
      const exploreBrowser = this.__dashboard.getExploreBrowser();
      [
        studyBrowser,
        exploreBrowser
      ].forEach(browser => {
        browser.addListener("startStudy", e => {
          const startStudyData = e.getData();
          this.__startStudy(startStudyData);
        }, this);
      });

      studyBrowser.addListener("updateTemplates", () => {
        exploreBrowser.reloadStudies();
      }, this);
    },

    __showDashboard: function() {
      if (!osparc.data.Permissions.getInstance().canDo("dashboard.read")) {
        // If guest fails to load study, log him out
        osparc.auth.Manager.getInstance().logout();
        return;
      }

      this.__mainStack.setSelection([this.__dashboardLayout]);
      this.__navBar.show();
      this.__navBar.setStudy(null);
      this.__navBar.setPageContext("dashboard");
      if (this.__studyEditor) {
        this.__studyEditor.destruct();
      }
    },

    __showLoadingPage: function(msg) {
      this.__loadingPage.setHeader(msg);
      this.__mainStack.setSelection([this.__loadingPage]);
    },

    __showStudyEditor: function(studyEditor) {
      if (this.__studyEditor) {
        this.__mainStack.remove(this.__studyEditor);
      }

      this.__studyEditor = studyEditor;
      this.__mainStack.add(this.__studyEditor);
      this.__mainStack.setSelection([this.__studyEditor]);
    },

    __startStudy: function(startStudyData) {
      const {
        studyId,
        pageContext
      } = startStudyData;
      this.__showLoadingPage(this.tr("Loading Study"));

      const params = {
        url: {
          "studyId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          if (!studyData) {
            const msg = this.tr("Study not found");
            throw new Error(msg);
          }
          this.__loadStudy(studyData, pageContext);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.__showDashboard();
          return;
        });
    },

    __startSnapshot: async function(studyId, snapshotId) {
      this.__showLoadingPage(this.tr("Loading Snapshot"));

      this.__loadingPage.setMessages([
        this.tr("Closing previous snapshot...")
      ]);
      this.__studyEditor.closeEditor();
      this.__closeStudy(studyId);
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
              this.__loadStudy(studyData);
            });
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.__showDashboard();
          return;
        });
    },

    __loadStudy: function(studyData, pageContext) {
      let locked = false;
      let lockedBy = false;
      if ("state" in studyData && "locked" in studyData["state"]) {
        locked = studyData["state"]["locked"]["value"];
        lockedBy = studyData["state"]["locked"]["owner"];
      }
      if (locked && lockedBy["user_id"] !== osparc.auth.Data.getInstance().getUserId()) {
        const msg = this.tr("Study is already open by ") + lockedBy["first_name"];
        throw new Error(msg);
      }
      const store = osparc.store.Store.getInstance();
      store.getInaccessibleServices(studyData)
        .then(inaccessibleServices => {
          if (inaccessibleServices.length) {
            this.__dashboard.getStudyBrowser().resetSelection();
            const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
            throw new Error(msg);
          }
          this.__showStudyEditor(this.__getStudyEditor());
          this.__studyEditor.setStudyData(studyData)
            .then(() => {
              this.__syncStudyEditor(pageContext);
            });
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.__showDashboard();
          return;
        });
    },

    __closeStudy: function(studyId) {
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
      studyEditor.addListener("expandNavBar", () => this.__navBar.show());
      studyEditor.addListener("collapseNavBar", () => this.__navBar.exclude());
      studyEditor.addListener("backToDashboardPressed", () => this.__backToDashboardPressed(), this);
      studyEditor.addListener("forceBackToDashboard", () => this.__showDashboard(), this);
      studyEditor.addListener("slidesEdit", () => {
        studyEditor.editSlides();
      }, this);
      studyEditor.addListener("slidesGuidedStart", () => {
        this.__navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
        studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
      }, this);
      studyEditor.addListener("slidesAppStart", () => {
        this.__navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[3]);
        studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[3]);
      }, this);
      studyEditor.addListener("slidesStop", () => {
        this.__navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
        this.__studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
      }, this);
      return studyEditor;
    },

    closeEditor: function() {
      if (this.__studyEditor) {
        this.__studyEditor.closeEditor();
      }
    }
  }
});
