qx.Class.define("qxapp.layout.PrjEditor", {
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

    let scope = this;
    this.__SettingsView.addListener("SettingsEditionDone", function() {
      scope.__showSettings(false);
    }, scope);

    this.__Workbench.addListener("NodeDoubleClicked", function(e) {
      scope.__showSettings(true);
      scope.__SettingsView.setNodeMetadata(e.getData());
    }, scope);
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
    },

    setData: function(newData) {
      this.__Workbench.setData(newData);
    }
  }
});
