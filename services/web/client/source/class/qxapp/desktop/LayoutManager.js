/* ************************************************************************

   qxapp - the simcore frontend

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
 *     - PrjBrowser
 *     - ServiceBrowser
 *     - DataManager
 *   - PrjEditor
 *
 * <pre class='javascript'>
 *   let layoutManager = new qxapp.desktop.LayoutManager();
 *   this.getRoot().add(layoutManager);
 * </pre>
 */

qx.Class.define("qxapp.desktop.LayoutManager", {
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

    qxapp.io.WatchDog.getInstance().startCheck();
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __dashboard: null,
    __prjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar().set({
        height: 100
      });

      navBar.addListener("dashboardPressed", () => {
        if (this.__prjEditor) {
          this.__prjEditor.updateProjectDocument();
        }
        this.__showDashboard();
      }, this);

      navBar.addListener("nodeDoubleClicked", e => {
        if (this.__prjEditor) {
          let nodeId = e.getData();
          this.__prjEditor.nodeSelected(nodeId, true);
        }
      }, this);
      return navBar;
    },

    __createMainView: function() {
      let prjStack = new qx.ui.container.Stack();

      let dashboard = this.__dashboard = new qxapp.desktop.Dashboard();
      dashboard.getPrjBrowser().addListener("startProject", e => {
        const projectEditor = e.getData();
        this.__showProjectEditor(projectEditor);
      }, this);
      prjStack.add(dashboard);

      return prjStack;
    },

    __showDashboard: function() {
      this.__prjStack.setSelection([this.__dashboard]);
      this.__dashboard.getPrjBrowser().reloadUserProjects();
      this.__navBar.setPathButtons([]);
      if (this.__prjEditor) {
        this.__prjEditor.destruct();
      }
    },

    __showProjectEditor: function(projectEditor) {
      if (this.__prjEditor) {
        this.__prjStack.remove(this.__prjEditor);
      }

      this.__prjEditor = projectEditor;
      let project = projectEditor.getProject();
      this.__prjStack.add(this.__prjEditor);
      this.__prjStack.setSelection([this.__prjEditor]);
      this.__navBar.setProject(project);
      this.__navBar.setPathButtons(project.getWorkbench().getPathIds("root"));

      this.__prjEditor.addListener("changeMainViewCaption", ev => {
        const elements = ev.getData();
        this.__navBar.setPathButtons(elements);
      }, this);

      this.__prjEditor.addListener("projectSaved", ev => {
        const wasSaved = ev.getData();
        if (wasSaved) {
          this.__navBar.projectSaved();
        }
      }, this);
    }
  }
});
