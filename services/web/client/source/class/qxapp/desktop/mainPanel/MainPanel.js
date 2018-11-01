/* eslint no-underscore-dangle: 0 */

qx.Class.define("qxapp.desktop.mainPanel.MainPanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    let controlsBar = this.__controlsBar = new qxapp.desktop.mainPanel.ControlsBar();
    controlsBar.set({
      height: 60,
      allowGrowY: false
    });

    let hBox = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
      allowGrowY: true
    });

    this._add(hBox, {
      flex: 1
    });
    this._add(controlsBar);
  },

  properties: {
    mainView: {
      nullable: false,
      check : "qx.ui.core.Widget",
      apply : "__applyMainView"
    }
  },

  members: {
    __mainView: null,
    __controlsBar: null,

    __applyMainView: function(newWidget) {
      this.__mainView.removeAll();
      this.__mainView.add(newWidget, {
        flex: 1
      });
    },

    getControls: function() {
      return this.__controlsBar;
    }
  }
});
