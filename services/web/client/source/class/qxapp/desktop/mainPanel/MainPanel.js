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

    this.__mainViewStack = new qx.ui.container.Stack();
    this.__mainView.add(this.__mainViewStack, {
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
      apply : "__applyMainView"
    }
  },

  members: {
    __mainView: null,
    __mainViewStack: null,
    __controlsBar: null,

    __applyMainView: function(newWidget) {
      let stack = this.__mainViewStack;
      let iFrameIdx = stack.indexOf(newWidget);
      if (iFrameIdx === -1) {
        stack.add(newWidget);
        iFrameIdx = stack.getChildren().length - 1;
      }
      stack.setSelection([stack.getChildren()[iFrameIdx]]);
    },

    getControls: function() {
      return this.__controlsBar;
    }
  }
});
