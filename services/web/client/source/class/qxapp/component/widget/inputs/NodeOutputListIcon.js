qx.Class.define("qxapp.component.widget.inputs.NodeOutputListIcon", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    let list = this.__list = new qx.ui.list.List().set({
      labelPath: "label",
      iconPath: "icon"
    });

    let that = this;
    list.setDelegate({
      createItem: () => new qxapp.component.widget.inputs.NodeOutputListItemIcon(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("thumbnail", "icon", null, item, id);
        c.bindProperty("label", "label", {
          converter: function(data, model, source, target) {
            // return "<b>" + data + "</b>";
            return data;
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
        that.__createDragMechanism(item); // eslint-disable-line no-underscore-dangle
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

    __createDragMechanism: function(item) {
      item.setDraggable(true);
      item.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");

        // HACK
        if (this.getNodeModel().getKey() === "services/demodec/dynamic/itis/s4l/Neuroman") {
          // Register supported types
          e.addType("osparc-port-link");
          item.nodeId = this.getNodeModel().getNodeId();
          item.portId = item.getLabel();
        } else {
          // Register supported types
          e.addType("osparc-mapping");
        }
      }, this);
    },

    getOutputWidget: function() {
      return this.__list;
    }
  }
});
