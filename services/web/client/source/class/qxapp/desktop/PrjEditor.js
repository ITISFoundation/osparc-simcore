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

    const settingsWidth = this.__settingsWidth = 500;
    let settingsView = this.__settingsView = new qxapp.components.workbench.SettingsView().set({
      maxWidth: settingsWidth,
      width: 0,
      minWidth: 0,
      visibility: "excluded"
    });

    settingsView.addListenerOnce("appear", () => {
      settingsView.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          settingsView.resetDecorator();
          if (settingsView.getWidth() === 0) {
            settingsView.exclude();
          }
        });
    });

    this.__pane.add(settingsView, 0);

    let workbench = this.__workbench = new qxapp.components.workbench.Workbench();
    workbench.addListenerOnce("appear", () => {
      workbench.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          workbench.resetDecorator();
        });
    });

    this.__pane.add(workbench, 1);



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
      let viewerWin = this.__createBrowserWindow(url, e.getData().label);
      this.__workbench.addWindowToDesktop(viewerWin);
    }, this);

    this.__settingsView.addListener("NodeProgress", function(e) {
      const nodeId = e.getData()[0];
      const progress = e.getData()[1];
      this.__workbench.updateProgress(nodeId, progress);
    }, this);

    this.__settingsView.addListener("SettingExposed", function(e) {
      const nodeId = e.getData()[0];
      const settingId = e.getData()[1];
      const expose = e.getData()[2];
      this.__workbench.settingExposed(nodeId, settingId, expose);
    }, this);

    this.__workbench.addListener("NodeDoubleClicked", function(e) {
      let node = e.getData();
      this.__settingsView.setNodeMetadata(node);
      this.__showSettings(true);
    }, this);

    this.__transDeco = new qx.ui.decoration.Decorator().set({
      transitionProperty: ["left", "right", "width"],
      transitionDuration: "0.1s",
      transitionTimingFunction: "ease"
    });
  },

  members: {
    __pane: null,
    __settingsView: null,
    __workbench: null,
    __settingsWidth: null,
    __transDeco: null,

    __showSettings: function(showSettings) {
      if (showSettings) {
        this.__settingsView.show();
      }
      qx.ui.core.queue.Manager.flush();
      this.__settingsView.set({
        decorator: this.__transDeco,
        width: showSettings ? Math.round(this.__settingsWidth * 0.75) : 0
      });
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
