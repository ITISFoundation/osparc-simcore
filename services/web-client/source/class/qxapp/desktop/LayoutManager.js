
qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__NavBar = this.__createNavigationBar();
    this.__NavBar.setHeight(100);
    this.add(this.__NavBar);

    this.__PrjStack = this.__getPrjStack();
    this.add(this.__PrjStack, {
      flex: 1
    });

    this.__NavBar.addListener("HomePressed", function() {
      this.__PrjStack.setSelection([this.__PrjBrowser]);
      this.__NavBar.setCurrentStatus("Browser");
    }, this);

    this.__PrjBrowser.addListener("StartPrj", function(e) {
      this.__PrjStack.setSelection([this.__PrjEditor]);
      this.__NavBar.setCurrentStatus(e.getData());
    }, this);
  },

  events: {},

  members: {
    __NavBar: null,
    __PrjStack: null,
    __PrjBrowser: null,
    __PrjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setCurrentStatus("Browser");
      return navBar;
    },

    __getPrjStack: function() {
      let prjStack = new qx.ui.container.Stack();

      this.__PrjBrowser = new qxapp.desktop.PrjBrowser();
      prjStack.add(this.__PrjBrowser);

      this.__PrjEditor = new qxapp.desktop.PrjEditor();
      prjStack.add(this.__PrjEditor);

      return prjStack;
    }
  }
});
