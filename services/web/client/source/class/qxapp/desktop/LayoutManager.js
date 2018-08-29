
qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__navBar = this.__createNavigationBar();
    this.__navBar.setHeight(100);
    this.add(this.__navBar);

    let prjStack = this.__prjStack = new qx.ui.container.Stack();

    this.__prjBrowser = new qxapp.desktop.PrjBrowser();
    prjStack.add(this.__prjBrowser);

    this.add(this.__prjStack, {
      flex: 1
    });

    this.__navBar.addListener("DashboardPressed", function() {
      this.__prjStack.setSelection([this.__prjBrowser]);
      this.__navBar.setMainViewCaption("Dashboard");
      this.__navBar.setProjectName("");
    }, this);

    this.__prjBrowser.addListener("StartProject", function(e) {
      let project = e.getData();
      if (this.__prjEditor) {
        this.__prjStack.remove(this.__prjEditor);
      }
      this.__prjEditor = new qxapp.desktop.PrjEditor(project.getProjectId());
      this.__prjStack.add(this.__prjEditor);
      this.__prjStack.setSelection([this.__prjEditor]);
      this.__navBar.setMainViewCaption("");
      this.__navBar.setProjectName(project.getName());
    }, this);
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __prjBrowser: null,
    __prjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setMainViewCaption("Dashboard");
      return navBar;
    }
  }
});
