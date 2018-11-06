qx.Class.define("qxapp.component.widget.inputs.NodeOutputListIcon", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    let list = this.__list = new qx.ui.list.List().set({
      labelPath: "label",
      iconPath: "icon",
      draggable: true
    });

    list.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputListItemIcon(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("thumbnail", "icon", null, item, id);
        c.bindProperty("label", "label", {
          converter: function(data, model, source, target) {
            return "<b>" + data + "</b>";
          }
        }, item, id);
      },
      configureItem: item => {
        let icon = item.getChildControl("icon");
        icon.set({
          scale: true,
          width: 246,
          height: 144
        });
        item.addListener("dragstart", e => {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-mapping");
        });
      }
    });

    const itemList = qxapp.data.Store.getInstance().getItemList(nodeModel.getNodeId(), portKey);
    const listModel = qxapp.data.Converters.fromAPIListToVirtualListModel(itemList);
    let model = qx.data.marshal.Json.createModel(listModel, true);
    list.setModel(model);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
    __list: null,

    getOutputWidget: function() {
      return this.__list;
    }
  }
});
