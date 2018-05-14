/* global window */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.Canvas()
    });

    // Create a horizontal split pane
    this.__pane = new qx.ui.splitpane.Pane("horizontal");

    const settingsWidth = 500;
    this.__settingsView = new qxapp.components.workbench.SettingsView();
    this.__settingsView.set({
      minWidth: settingsWidth*0.5,
      maxWidth: settingsWidth,
      width: settingsWidth*0.75
    });
    this.__pane.add(this.__settingsView, 0);

    this.__workbench = new qxapp.components.workbench.Workbench();
    this.__pane.add(this.__workbench, 1);

    this.add(this.__pane, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__showSettings(false);

    this.__settingsView.addListener("SettingsEditionDone", function() {
      this.__showSettings(false);
    }, this);

    this.__settingsView.addListener("ShowViewer", function(e) {
      let url = "http://" + window.location.hostname + ":" + e.getData().viewer.port;
      let viewerWin = this.__createBrowserWindow(url, e.getData().name);
      this.__workbench.addWindowToDesktop(viewerWin);
    }, this);

    this.__workbench.addListener("NodeDoubleClicked", function(e) {
      this.__showSettings(true);
      this.__settingsView.setNodeMetadata(e.getData());
    }, this);
  },

  members: {
    __pane: null,
    __settingsView: null,
    __workbench: null,

    __showSettings: function(showSettings) {
      if (showSettings) {
        this.__settingsView.show();
        this.__workbench.show();
      } else {
        this.__settingsView.exclude();
        this.__workbench.show();
      }
    },

    __createBrowserWindow: function(url, name) {
      console.log("Accessing:", url);
      let win = new qx.ui.window.Window(name);
      win.setShowMinimize(false);
      win.setLayout(new qx.ui.layout.VBox(5));
      let iframe = new qx.ui.embed.Iframe().set({
        width: 900,
        height: 700,
        minWidth: 500,
        minHeight: 500,
        source: url,
        decorator : null
      });
      win.add(iframe, {
        flex: 1
      });
      // win.setModal(true);
      win.moveTo(150, 150);

      return win;
    },

    setData: function(newData) {
      this.__workbench.setData(newData);
    }
  }
});
