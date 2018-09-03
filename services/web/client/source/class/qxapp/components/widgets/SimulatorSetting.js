qx.Class.define("qxapp.components.widgets.SimulatorSetting", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let simulatorSettingLayout = new qx.ui.layout.HBox(10);
    this._setLayout(simulatorSettingLayout);

    let treesBox = this.__treesBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: 300
    });
    this._add(treesBox);

    let contentBox = this.__contentBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(contentBox, {
      flex: 1
    });
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

      for (const portKey in node.getInputPorts()) {
        const port = node.getInputPort(portKey);
        console.log(port);
        const portType = port.portType;
        if (portType.includes("data:application/s4l-api")) {
          const apiType = portType.split("/").pop();
          if (apiType !== "settings") {
            const inputLabel = portKey;
            let tree = new qx.ui.tree.Tree().set({
              width: 300,
              selectionMode: "single"
            });
            let root = new qx.ui.tree.TreeFolder(inputLabel);
            root.setOpen(true);
            tree.setRoot(root);
            this.__treesBox.add(tree, {
              flex: 1
            });
          }
        }
      }
    }
  }
});
