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
 * - Main View (Stack).
 *   - Dashboard (Stack):
 *     - StudyBrowser
 *     - ServiceBrowser
 *     - DataManager
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

    let navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    let prjStack = this.__prjStack = this.__createMainView();
    this._add(prjStack, {
      flex: 1
    });
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __dashboard: null,
    __dashboardLayout: null,
    __studyEditor: null,

    __createNavigationBar: function() {
      let navBar = new osparc.desktop.NavigationBar().set({
        height: 100
      });

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

    __createMainView: function() {
      const prjStack = new qx.ui.container.Stack();

      const nStudyItemsPerRow = 5;
      const studyButtons = osparc.dashboard.StudyBrowserButtonBase;
      const dashboard = this.__dashboard = new osparc.dashboard.Dashboard().set({
        width: nStudyItemsPerRow * (studyButtons.ITEM_WIDTH + studyButtons.SPACING) + 25 // padding + scrollbar
      });
      dashboard.getStudyBrowser().addListener("startStudy", e => {
        const studyEditor = e.getData();
        this.__startStudyEditor(studyEditor);
      }, this);

      const dashboardLayout = this.__dashboardLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      dashboardLayout.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      dashboardLayout.add(dashboard);
      dashboardLayout.add(new qx.ui.core.Widget(), {
        flex: 1
      });

      prjStack.add(dashboardLayout);

      return prjStack;
    },

    __showDashboard: function() {
      this.__prjStack.setSelection([this.__dashboardLayout]);
      this.__dashboard.getStudyBrowser().reloadUserStudies();
      this.__navBar.setPathButtons([]);
      if (this.__studyEditor) {
        this.__studyEditor.destruct();
      }
    },

    __startStudyEditor: function(studyEditor) {
      if (this.__studyEditor) {
        this.__prjStack.remove(this.__studyEditor);
      }

      this.__studyEditor = studyEditor;
      let study = studyEditor.getStudy();
      this.__prjStack.add(this.__studyEditor);
      this.__prjStack.setSelection([this.__studyEditor]);
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
    }
  }
});
