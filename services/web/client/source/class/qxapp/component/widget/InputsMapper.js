/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "allow": ["__willBeBranch", "__willBeLeaf", "__tree"] }] */

qx.Class.define("qxapp.component.widget.InputsMapper", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, mapper) {
    this.base();

    let widgetLayout = new qx.ui.layout.VBox(5);
    this._setLayout(widgetLayout);

    this.setNodeModel(nodeModel);
    this.setMapper(mapper);

    let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
      openMode: "none"
    });
    this._add(tree, {
      flex: 1
    });
    tree.getSelection().addListener("change", this.__onTreeSelectionChanged, this);

    let that = this;
    tree.setDelegate({
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        // c.bindProperty("key", "key", null, item, id);
      },
      configureItem: item => {
        item.setDroppable(true);
        item.addListener("dragover", e => {
          let compatible = false;
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const fromKey = from.getNodeKey();
            if (that.__willBeBranch(fromKey) || that.__willBeLeaf(fromKey)) {
              compatible = true;
            }
          }
          if (!compatible) {
            e.preventDefault();
          }
        });
        item.addListener("drop", e => {
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const fromNodeKey = from.getNodeKey();
            const fromPortKey = from.getPortKey();
            const willBeBranch = that.__willBeBranch(fromNodeKey);
            let data = {
              key: from.getModel(),
              label: from.getLabel()
            };
            if (willBeBranch) {
              data["children"] = [];
            }
            let newItem = qx.data.marshal.Json.createModel(data, true);
            newItem["nodeKey"] = fromNodeKey;
            newItem["portKey"] = fromPortKey;
            const to = e.getCurrentTarget().getModel();
            to.getChildren().push(newItem);
            if (willBeBranch) {
              const nodeInstanceUUID = null;
              const itemProps = qxapp.data.Store.getInstance().getItem(nodeInstanceUUID, fromPortKey, newItem.getKey());
              if (itemProps) {
                let form = new qxapp.component.form.Auto(itemProps);
                let propsWidget = new qxapp.component.form.renderer.PropForm(form);
                newItem["propsWidget"] = propsWidget;
              }
            }
            tree.focus();
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

    __willBeBranch: function(candidate) {
      let isBranch = false;
      const maps = this.getMapper().maps;
      if (Object.prototype.hasOwnProperty.call(maps, "branch")) {
        if (maps["branch"] === candidate) {
          isBranch = true;
        }
      }
      const isDefault = candidate === this.getNodeModel().getKey();
      return isDefault || isBranch;
    },

    __willBeLeaf: function(candidate) {
      let isLeave = false;
      const maps = this.getMapper().maps;
      if (Object.prototype.hasOwnProperty.call(maps, "leaf")) {
        if (maps["leaf"] === candidate) {
          isLeave = true;
        }
      }
      return isLeave;
    },

    __onTreeSelectionChanged: function() {
      // remove all but the tree
      while (this._getChildren().length > 1) {
        this._removeAt(1);
      }
      let selectedItems = this.__tree.getSelection();
      if (selectedItems.length < 1) {
        return;
      }
      let selectedItem = selectedItems.toArray()[0];
      if (Object.prototype.hasOwnProperty.call(selectedItem, "propsWidget")) {
        this._add(selectedItem["propsWidget"]);
      }
    }
  }
});
