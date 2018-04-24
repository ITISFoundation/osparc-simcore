/* global qxapp */
/* global window */
/* global document */

qx.Class.define("qxapp.layout.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      width: this._getDocWidth(),
      height: this._getDocHeight()
    });

    this.set({
      layout: new qx.ui.layout.Canvas()
    });

    // Create a horizontal split pane
    this._pane = new qx.ui.splitpane.Pane("horizontal");

    const settingsWidth = 500;
    this._settingsView = new qxapp.components.SettingsView();
    this._settingsView.set({
      minWidth: settingsWidth*0.5,
      maxWidth: settingsWidth,
      width: settingsWidth*0.75
    });
    this._pane.add(this._settingsView, 0);

    this._workbench = new qxapp.components.Workbench();
    this._pane.add(this._workbench, 1);

    this.add(this._pane, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this._showSettings(false);

    let scope = this;
    this._settingsView.addListener("SettingsEditionDone", function() {
      scope._showSettings(false);
    }, scope);

    this._workbench.addListener("NodeDoubleClicked", function(e) {
      scope._showSettings(true);
      scope._settingsView.setNodeMetadata(e.getData());
    }, scope);

    window.addEventListener("resize", function() {
      scope.set({
        width: scope._getDocWidth(),
        height: scope._getDocHeight()
      });
    }, scope);
  },

  events: {

  },

  members: {
    _pane: null,

    _getDocWidth: function() {
      let body = document.body;
      let html = document.documentElement;
      let docWidth = Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth);
      return docWidth;
    },

    _getDocHeight: function() {
      let body = document.body;
      let html = document.documentElement;
      let docHeight = Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight, html.offsetHeight);
      return docHeight;
    },

    _showSettings: function(showSettings) {
      if (showSettings) {
        this._settingsView.show();
        this._workbench.show();
      } else {
        this._settingsView.exclude();
        this._workbench.show();
      }
    }
  },

  destruct: function() {
    this._disposeObjects("_pane", "_settingsView", "_workbench");
  }
});
