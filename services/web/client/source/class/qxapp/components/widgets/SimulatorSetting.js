qx.Class.define("qxapp.components.widgets.SimulatorSetting", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let simulatorSettingLayout = new qx.ui.layout.HBox(10);
    this._setLayout(simulatorSettingLayout);

    let treesBox = this.__treesBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(treesBox);

    let contentBox = this.__contentBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(contentBox);
  },

  properties: {
    node: {
      check: "qxapp.components.workbench.NodeBase",
      apply: "__applyNode"
    }
  },

  events: {},

  members: {
    __treesBox: null,
    __contentBox: null,

    __applyNode: function(node, oldNode, propertyName) {
      this.__treesBox.removeAll();
      this.__contentBox.removeAll();

      console.log(node);
    }
  }
});
