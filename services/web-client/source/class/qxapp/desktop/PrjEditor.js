
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.Canvas()
    });

    // Create a horizontal split pane
    this.__Pane = new qx.ui.splitpane.Pane("horizontal");

    const settingsWidth = this.__SettingsWidth = 500;
    let settingsView = this.__SettingsView = new qxapp.components.workbench.SettingsView().set({
      // minWidth: settingsWidth*0.5,
      maxWidth: settingsWidth,
      width: 0,
      minWidth: 0,
      visibility: "excluded"
    });
    settingsView.addListenerOnce("appear", () => {
      settingsView.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          console.log(settingsView.getWidth());
          settingsView.resetDecorator();
          if (settingsView.getWidth() === 0) {
            settingsView.exclude();
          }
        });
    });

    this.__Pane.add(settingsView, 0);

    let workbench = this.__Workbench = new qxapp.components.workbench.Workbench();
    workbench.addListenerOnce("appear", () => {
      workbench.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          console.log(workbench.getWidth());
          workbench.resetDecorator()
        });
    });

    this.__Pane.add(this.__Workbench, 1);

    this.add(this.__Pane, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });
    this.__showSettings(false);

    this.__SettingsView.addListener("SettingsEditionDone", () => {
      this.__showSettings(false);
    }, this);

    this.__Workbench.addListener("NodeDoubleClicked", e => {
      this.__showSettings(true);
      this.__SettingsView.setNodeMetadata(e.getData());
    }, this);

    this.__TransDeco = new qx.ui.decoration.Decorator().set({
      transitionProperty: ["left","right","width"],
      transitionDuration: "0.1s",
      transitionTimingFunction: "ease"
    });
  },

  members: {
    __Pane: null,
    __SettingsView: null,
    __Workbench: null,
    __SettingsWidth: null,
    __TransDeco: null,
    __showSettings: function(showSettings) {
      if (showSettings) {
        this.__SettingsView.show();
      }
      qx.ui.core.queue.Manager.flush();
      this.__SettingsView.set({
        decorator: this.__TransDeco,
        width: showSettings ? Math.round(this.__SettingsWidth * 0.75) : 0
      });
    }
  }
});
