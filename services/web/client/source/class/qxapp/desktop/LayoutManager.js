
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

    this.__prjStack = this.__getPrjStack();
    this.add(this.__prjStack, {
      flex: 1
    });

    this.__navBar.addListener("HomePressed", function() {
      this.__prjStack.setSelection([this.__prjBrowser]);
      this.__navBar.setCurrentStatus("Browser");
    }, this);

    this.__prjBrowser.addListener("StartPrj", function(e) {
      this.__prjStack.setSelection([this.__PrjEditor]);
      this.__navBar.setCurrentStatus(e.getData().getName());
      // this.__PrjEditor.showSettings(false);
      this.__PrjEditor.setData(qxapp.dev.fake.Data.getPrjData(e.getData().getPrjId()));
    }, this);
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __prjBrowser: null,
    __PrjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setCurrentStatus("Browser");
      return navBar;
    },

    __getPrjStack: function() {
      let prjStack = new qx.ui.container.Stack();

      this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      prjStack.add(this.__prjBrowser);

      this.__PrjEditor = new qxapp.desktop.PrjEditor();
      prjStack.add(this.__PrjEditor);

      return prjStack;
    }
  }
});
