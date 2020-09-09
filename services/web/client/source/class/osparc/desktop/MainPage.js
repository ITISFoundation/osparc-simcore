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
 *   let layoutManager = new osparc.desktop.MainPage();
 *   this.getRoot().add(layoutManager);
 * </pre>
 */

qx.Class.define("osparc.desktop.MainPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

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
      const navBar = new osparc.desktop.NavigationBar();

      navBar.addListener("dashboardPressed", () => {
        if (!osparc.data.Permissions.getInstance().canDo("studies.user.create", true)) {
          return;
        }
        if (this.__studyEditor) {
          this.__studyEditor.updateStudyDocument(false, this.__studyEditor.closeStudy);
        }
        this.__showDashboard();
      }, this);

      navBar.addListener("nodeSelected", e => {
        if (this.__studyEditor) {
          let nodeId = e.getData();
          this.__studyEditor.nodeSelected(nodeId);
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
          const studyId = e.getData();
          this.__startStudy(studyId);
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
        return;
      }

      this.__mainStack.setSelection([this.__dashboardLayout]);
      this.__dashboard.getStudyBrowser().reloadUserStudies();
      this.__navBar.setPathButtons([]);
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

    __startStudy: function(studyId) {
      this.__showLoadingPage(this.tr("Loading Study"));

      const store = osparc.store.Store.getInstance();
      store.getStudyWState(studyId, true)
        .then(latestStudyData => {
          if (!latestStudyData) {
            const msg = this.tr("Study not found");
            throw new Error(msg);
          }
          const locked = ("locked" in latestStudyData) ? latestStudyData["locked"]["value"] : false;
          if (locked) {
            const msg = this.tr("Study is opened");
            throw new Error(msg);
          }
          store.getInaccessibleServices(latestStudyData)
            .then(inaccessibleServices => {
              if (inaccessibleServices.length) {
                this.__dashboard.getStudyBrowser().resetSelection();
                const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
                throw new Error(msg);
              }
              this.__showStudyEditor(this.__getStudyEditor());
              this.__studyEditor.setStudy(latestStudyData)
                .then(() => {
                  this.__syncStudyEditor();
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

    __syncStudyEditor: function() {
      const studyEditor = this.__studyEditor;
      const study = studyEditor.getStudy();
      this.__navBar.setStudy(study);
      this.__navBar.setPathButtons(this.__studyEditor.getCurrentPathIds());

      this.__studyEditor.addListener("changeMainViewCaption", ev => {
        const elements = ev.getData();
        this.__navBar.setPathButtons(elements);
      }, this);

      this.__studyEditor.addListener("studyIsLocked", () => {
        this.__showDashboard();
      }, this);

      this.__studyEditor.addListener("studySaved", ev => {
        const wasSaved = ev.getData();
        if (wasSaved) {
          this.__navBar.studySaved();
        }
      }, this);
    },

    __getStudyEditor: function() {
      const studyEditor = this.__studyEditor || new osparc.desktop.StudyEditor();
      studyEditor.addListenerOnce("startStudy", e => {
        const studyId = e.getData();
        this.__startStudy(studyId);
      }, this);
      return studyEditor;
    }
  }
});
