
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.Canvas()
    });

    // Create a horizontal split pane
    this.__Pane = new qx.ui.splitpane.Pane("horizontal");

    const settingsWidth = 500;
    this.__SettingsView = new qxapp.components.workbench.SettingsView();
    this.__SettingsView.set({
      minWidth: settingsWidth*0.5,
      maxWidth: settingsWidth,
      width: settingsWidth*0.75
    });
    this.__Pane.add(this.__SettingsView, 0);

    this.__Workbench = new qxapp.components.workbench.Workbench();
    this.__Pane.add(this.__Workbench, 1);

    this.add(this.__Pane, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__showSettings(false);

    this.__SettingsView.addListener("SettingsEditionDone", function() {
      this.__showSettings(false);
    }, this);

    this.__Workbench.addListener("NodeDoubleClicked", function(e) {
      this.__showSettings(true);
      this.__SettingsView.setNodeMetadata(e.getData());
    }, this);
  },

  members: {
    __Pane: null,
    __SettingsView: null,
    __Workbench: null,

    __showSettings: function(showSettings) {
      if (showSettings) {
        this.__SettingsView.show();
        this.__Workbench.show();
      } else {
        this.__SettingsView.exclude();
        this.__Workbench.show();
      }
    }
  }
});
