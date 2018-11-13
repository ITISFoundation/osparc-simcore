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
      createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        // c.bindProperty("key", "key", null, item, id);
        c.bindProperty("isDir", "isDir", null, item, id);
        c.bindProperty("isRoot", "isRoot", null, item, id);
      },
      configureItem: item => {
        item.set({
          droppable: true
        });
        item.addListener("dragover", e => {
          item.set({
            droppable: item.getIsDir()
          });
          let compatible = false;
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const to = e.getCurrentTarget();
            const fromKey = from.getNodeKey();
            if (to.getIsRoot()) {
              // root
              compatible = from.getIsDir() && that.__willBeBranch(fromKey);
            } else {
              // non root
              compatible = to.getIsDir() && !from.getIsDir() && that.__willBeLeaf(fromKey);
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
            let data = {
              key: from.getModel(),
              label: from.getLabel(),
              nodeKey: from.getNodeKey(),
              portKey: from.getPortKey(),
              isDir: from.getIsDir()
            };
            const willBeBranch = that.__willBeBranch(fromNodeKey);
            if (willBeBranch) {
              data["children"] = [];
            }
            let newItem = qx.data.marshal.Json.createModel(data, true);
            const to = e.getCurrentTarget();
            to.getModel().getChildren()
              .push(newItem);
            if (willBeBranch) {
              const nodeInstanceUUID = null;
              const itemProps = qxapp.data.Store.getInstance().getItem(nodeInstanceUUID, fromPortKey, newItem.getKey());
              if (itemProps) {
                let form = new qxapp.component.form.Auto(itemProps, this.getNodeModel());
                let propsWidget = new qxapp.component.form.renderer.PropForm(form);
                newItem["propsWidget"] = propsWidget;
              }
            }
            to.setOpen(true);
            tree.focus();
          }
        });
      }
    });

    let data = {
      label: nodeModel.getLabel(),
      isRoot: true,
      children: []
    };
    let model = qx.data.marshal.Json.createModel(data, true);
    tree.setModel(model);

    this.addListener("keypress", function(keyEvent) {
      let treeSelection = this.__tree.getSelection();
      if (treeSelection.length < 1) {
        return;
      }
      let selectedItem = treeSelection.toArray()[0];
      if (selectedItem.getIsRoot && selectedItem.getIsRoot()) {
        return;
      }
      switch (keyEvent.getKeyIdentifier()) {
        case "F2": {
          let treeItemRenamer = new qxapp.component.widget.TreeItemRenamer(selectedItem);
          treeItemRenamer.addListener("LabelChanged", e => {
            let newLabel = e.getData()["newLabel"];
            selectedItem.setLabel(newLabel);
          }, this);
          treeItemRenamer.center();
          treeItemRenamer.open();
          break;
        }
        case "Delete": {
          let branches = this.__tree.getModel().getChildren();
          // branch
          let removed = branches.remove(selectedItem);
          if (!removed) {
            // leaf
            let br = branches.toArray();
            for (let i=0; i<br.length; i++) {
              let branch = br[i];
              removed = branch.getChildren().remove(selectedItem);
              if (removed) {
                break;
              }
            }
          }
          break;
        }
      }
    }, this);
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
