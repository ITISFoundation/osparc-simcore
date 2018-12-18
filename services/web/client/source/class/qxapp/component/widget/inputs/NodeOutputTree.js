qx.Class.define("qxapp.component.widget.inputs.NodeOutputTree", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children");

    tree.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        // c.bindProperty("key", "model", null, item, id);
      },
      configureItem: item => {
        item.set({
          isDir: !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting"),
          nodeKey: nodeModel.getKey(),
          portKey: portKey,
          draggable: true
        });
        item.addListener("dragstart", e => {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-mapping");
        });
      }
    });

    const itemList = qxapp.data.Store.getInstance().getItemList(nodeModel.getKey(), portKey);
    const showAsDirs = !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting");
    const children = qxapp.data.Converters.fromAPITreeToVirtualTreeModel(itemList, showAsDirs);
    let data = {
      label: port.label,
      children: children
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
    __tree: null,

    getOutputWidget: function() {
      return this.__tree;
    }
  }
});
