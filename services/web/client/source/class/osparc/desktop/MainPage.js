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

  construct: function(studyId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    let navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    let prjStack = this.__prjStack = this.__createMainView(studyId);
    this._add(prjStack, {
      flex: 1
    });
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __dashboard: null,
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
          this.__studyEditor.updateStudyDocument();
          this.__studyEditor.closeStudy();
        }
        this.__showDashboard();
      }, this);

      navBar.addListener("nodeDoubleClicked", e => {
        if (this.__studyEditor) {
          let nodeId = e.getData();
          this.__studyEditor.nodeSelected(nodeId, true);
        }
      }, this);
      return navBar;
    },

    __createMainView: function(studyId) {
      let prjStack = new qx.ui.container.Stack();

      let dashboard = this.__dashboard = new osparc.desktop.Dashboard(studyId);
      dashboard.getStudyBrowser().addListener("startStudy", e => {
        const studyEditor = e.getData();
        this.__showStudyEditor(studyEditor);
      }, this);
      prjStack.add(dashboard);

      return prjStack;
    },

    __showDashboard: function() {
      this.__prjStack.setSelection([this.__dashboard]);
      this.__dashboard.getStudyBrowser().reloadUserStudies();
      this.__navBar.setPathButtons([]);
      if (this.__studyEditor) {
        this.__studyEditor.destruct();
      }
    },

    __showStudyEditor: function(studyEditor) {
      if (this.__studyEditor) {
        this.__prjStack.remove(this.__studyEditor);
      }

      this.__studyEditor = studyEditor;
      let study = studyEditor.getStudy();
      this.__prjStack.add(this.__studyEditor);
      this.__prjStack.setSelection([this.__studyEditor]);
      this.__navBar.setStudy(study);
      this.__navBar.setPathButtons(study.getWorkbench().getPathIds("root"));

      this.__studyEditor.addListener("changeMainViewCaption", ev => {
        const elements = ev.getData();
        this.__navBar.setPathButtons(elements);
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
