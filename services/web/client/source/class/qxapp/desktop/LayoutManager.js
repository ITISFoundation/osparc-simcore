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

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__navBar = this.__createNavigationBar();
    this.__navBar.setHeight(100);
    this.__navBar.addListener("nodeDoubleClicked", e => {
      if (this.__prjEditor) {
        let nodeId = e.getData();
        this.__prjEditor.nodeSelected(nodeId);
      }
    }, this);
    this.add(this.__navBar);

    let prjStack = this.__prjStack = new qx.ui.container.Stack();
    this.add(prjStack, {
      flex: 1
    });

    this.__createMainLayout();
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __dashboard: null,
    __prjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setMainViewCaption("Dashboard");
      return navBar;
    },

    __createMainLayout: function() {
      this.__dashboard = new qxapp.desktop.Dashboard();
      this.__prjStack.add(this.__dashboard);

      this.__navBar.addListener("dashboardPressed", function() {
        this.__prjEditor.updateProjectDocument();
        this.__showDashboard();
      }, this);

      this.__dashboard.getPrjBrowser().addListener("startProject", e => {
        const projectEditor = e.getData();
        this.__showProjectEditor(projectEditor);
      }, this);
    },

    __showDashboard: function() {
      this.__prjStack.setSelection([this.__dashboard]);
      this.__dashboard.getPrjBrowser().reloadUserProjects();
      this.__navBar.setMainViewCaption(this.tr("Dashboard"));
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
      this.__navBar.setMainViewCaption(project.getWorkbench().getPathIds("root"));

      this.__prjEditor.addListener("changeMainViewCaption", function(ev) {
        const elements = ev.getData();
        this.__navBar.setMainViewCaption(elements);
      }, this);
    }
  }
});
