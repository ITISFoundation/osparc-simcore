qx.Class.define("qxapp.desktop.mainPanel.MainPanel", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    let optionsBar = this.__optionsBar = new qxapp.desktop.mainPanel.OptionsBar();
    let mainView = new qx.ui.core.Widget();
    let controlsBar = this.__controlsBar = new qxapp.desktop.mainPanel.ControlsBar();

    optionsBar.set({
      width: 60,
      allowGrowX: false
    });

    controlsBar.set({
      height: 60,
      allowGrowY: false
    });

    let hBox = this.__hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    hBox.add(optionsBar);
    hBox.add(mainView, {
      flex: 1
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
      apply : "_applyMainView"
    }
  },

  events: {},

  members: {
    __hBox: null,
    __optionsBar: null,
    __controlsBar: null,

    _applyMainView: function(newWidget) {
      this.__hBox._removeAt(1);
      this.__hBox._addAt(newWidget, 1);
    },

    getOptions: function() {
      return this.__optionsBar;
    },

    getControls: function() {
      return this.__controlsBar;
    }
  }
});
