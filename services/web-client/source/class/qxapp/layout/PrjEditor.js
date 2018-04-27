/* global document */

qx.Class.define("qxapp.layout.PrjEditor", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.Canvas()
    });

    // Create a horizontal split pane
    this._Pane = new qx.ui.splitpane.Pane("horizontal");

    const settingsWidth = 500;
    this._SettingsView = new qxapp.components.workbench.SettingsView();
    this._SettingsView.set({
      minWidth: settingsWidth*0.5,
      maxWidth: settingsWidth,
      width: settingsWidth*0.75
    });
    this._Pane.add(this._SettingsView, 0);

    this._Workbench = new qxapp.components.workbench.Workbench();
    this._Pane.add(this._Workbench, 1);

    this.add(this._Pane, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this._showSettings(false);

    let scope = this;
    this._SettingsView.addListener("SettingsEditionDone", function() {
      scope._showSettings(false);
    }, scope);

    this._Workbench.addListener("NodeDoubleClicked", function(e) {
      scope._showSettings(true);
      scope._SettingsView.setNodeMetadata(e.getData());
    }, scope);

    /*
    window.addEventListener("resize", function() {
      scope.set({
        width: scope._getDocWidth(),
        height: scope._getDocHeight()
      });
    }, scope);
    */
  },

  members: {
    _Pane: null,
    _SettingsView: null,
    _Workbench: null,

    _getDocWidth: function() {
      let body = document.body;
      let html = document.documentElement;
      let docWidth = Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth);
      return docWidth;
    },

    _showSettings: function(showSettings) {
      if (showSettings) {
        this._SettingsView.show();
        this._Workbench.show();
      } else {
        this._SettingsView.exclude();
        this._Workbench.show();
      }
    }
  }
});
