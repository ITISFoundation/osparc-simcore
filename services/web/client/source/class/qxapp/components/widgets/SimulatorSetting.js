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

    let contentBox = this.__contentBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: 300
    });
    this._add(contentBox);

    let logo = new qx.ui.basic.Image("qxapp/modelerMockup.png").set({
      maxHeight: 438,
      maxWidth: 386,
      scale: true,
      alignX: "center",
      alignY: "middle"
    });
    this._add(logo, {
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
      for (const portKey in node.getInputPorts()) {
        const port = node.getInputPort(portKey);
        console.log(port);
        const portType = port.portType;
        if (portType.includes("data:application/s4l-api")) {
          const apiType = portType.split("/").pop();
          if (apiType !== "settings") {
            const inputLabel = portKey;
            let tree = new qx.ui.tree.Tree().set({
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

      this.__contentBox.removeAll();
      {
        let tree = new qx.ui.tree.Tree().set({
          selectionMode: "single"
        });
        let root = new qx.ui.tree.TreeFolder("Settings");
        root.setOpen(true);
        tree.setRoot(root);
        this.__contentBox.add(tree, {
          flex: 1
        });
      }
    },

    listClicked: function() {
      const index = this._indexOf(this.__treesBox);
      if (index > -1) {
        this._remove(this.__treesBox);
      } else {
        this._addAt(this.__treesBox, 0);
      }
    }
  }
});
