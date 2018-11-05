qx.Class.define("qxapp.component.widget.InputsMapper", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, mapper) {
    this.base();

    this.setNodeModel(nodeModel);
    this.setMapper(mapper);

    let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
      openMode: "none"
    });

    let that = this;
    tree.setDelegate({
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
      },
      configureItem: item => {
        item.setDroppable(true);
        item.addListener("dragover", e => {
          let compatible = false;
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            if (Object.prototype.hasOwnProperty.call(from, "nodeKey")) {
              const fromKey = from["nodeKey"];
              const maps = that.getMapper().maps;
              if (Object.values(maps).includes(fromKey) ||
                fromKey === that.getNodeModel().getKey()) {
                compatible = true;
              }
            }
          }
          if (!compatible) {
            e.preventDefault();
          }
        });
        item.addListener("drop", e => {
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const to = e.getCurrentTarget();
            if (Object.prototype.hasOwnProperty.call(from, "portKey")) {
              console.log("Map", from.getModel(), "to", to.getModel());
            }
          }
        });
      }
    });

    let data = {
      label: nodeModel.getLabel(),
      children: []
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    },

    mapper: {
      nullable: false
    }
  },

  members: {
    __tree: null,

    getWidget: function() {
      return this.__tree;
    }
  }
});
