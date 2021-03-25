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

      navBar.addListener("dashboardPressed", () => {
        if (!osparc.data.Permissions.getInstance().canDo("studies.user.create", true)) {
          return;
        }
        if (this.__studyEditor) {
          const dashboardBtn = navBar.getChildControl("dashboard-button");
          dashboardBtn.setFetching(true);
          const studyId = this.__studyEditor.getStudy().getUuid();
          this.__studyEditor.updateStudyDocument()
            .then(() => {
              this.__studyEditor.closeEditor();
              const reloadUserStudiesPromise = this.__showDashboard();
              reloadUserStudiesPromise
                .then(() => {
                  this.__closeStudy(studyId);
                });
            })
            .finally(() => {
              dashboardBtn.setFetching(false);
            });
        } else {
          this.__showDashboard();
        }
      }, this);

      navBar.addListener("slidesStart", () => {
        if (this.__studyEditor) {
          navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
          this.__studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[2]);
        }
      }, this);

      navBar.addListener("slidesStop", () => {
        if (this.__studyEditor) {
          navBar.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
          this.__studyEditor.setPageContext(osparc.navigation.NavigationBar.PAGE_CONTEXT[1]);
        }
      }, this);

      return navBar;
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
      const nStudyItemsPerRow = 5;
      const studyButtons = osparc.dashboard.StudyBrowserButtonBase;
      const dashboard = this.__dashboard = new osparc.dashboard.Dashboard().set({
        width: nStudyItemsPerRow * (studyButtons.ITEM_WIDTH + studyButtons.SPACING) // padding + scrollbar
      });
      const sideSearch = new osparc.dashboard.SideSearch();
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
        exploreBrowser.reloadTemplates();
      }, this);
    },

    __showDashboard: function() {
      if (osparc.data.Permissions.getInstance().getRole() === "guest") {
        // If guest fails to load study, log him out
        osparc.auth.Manager.getInstance().logout();
        return null;
      }

      this.__mainStack.setSelection([this.__dashboardLayout]);
      const studiesPromise = this.__dashboard.getStudyBrowser().reloadUserStudies();
      this.__navBar.setStudy(null);
      this.__navBar.setPageContext("dashboard");
      if (this.__studyEditor) {
        this.__studyEditor.destruct();
      }
      return studiesPromise;
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
          "projectId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(latestStudyData => {
          if (!latestStudyData) {
            const msg = this.tr("Study not found");
            throw new Error(msg);
          }

          let locked = false;
          let lockedBy = false;
          if ("state" in latestStudyData && "locked" in latestStudyData["state"]) {
            locked = latestStudyData["state"]["locked"]["value"];
            lockedBy = latestStudyData["state"]["locked"]["owner"];
          }
          if (locked && lockedBy["user_id"] !== osparc.auth.Data.getInstance().getUserId()) {
            const msg = this.tr("Study is already open by ") + lockedBy["first_name"];
            throw new Error(msg);
          }
          const store = osparc.store.Store.getInstance();
          store.getInaccessibleServices(latestStudyData)
            .then(inaccessibleServices => {
              if (inaccessibleServices.length) {
                this.__dashboard.getStudyBrowser().resetSelection();
                const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
                throw new Error(msg);
              }
              this.__showStudyEditor(this.__getStudyEditor());
              this.__studyEditor.setStudyData(latestStudyData)
                .then(() => {
                  this.__syncStudyEditor(pageContext);
                });
            })
            .catch(err => {
              osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
              this.__showDashboard();
              return;
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
          projectId: studyId
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "close", params);
    },

    __syncStudyEditor: function(pageContext) {
      const studyEditor = this.__studyEditor;
      const study = studyEditor.getStudy();
      this.__navBar.setStudy(study);
      if (pageContext === "slideshow") {
        this.__navBar.setPageContext("slideshow");
        studyEditor.setPageContext("slideshow");
      } else {
        this.__navBar.setPageContext("workbench");
        studyEditor.setPageContext("workbench");
      }

      this.__studyEditor.addListener("forceBackToDashboard", () => {
        this.__showDashboard();
      }, this);
    },

    __getStudyEditor: function() {
      const studyEditor = this.__studyEditor || new osparc.desktop.StudyEditor();
      studyEditor.addListenerOnce("startStudy", e => {
        const startStudyData = e.getData();
        this.__startStudy(startStudyData);
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
