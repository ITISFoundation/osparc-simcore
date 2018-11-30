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
      createItem: () => new qxapp.component.widget.InputsMapperTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
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
              // HACK
              if (from.getLabel() === "20181113_Yoon-sun_V4_preview") {
                compatible = true;
              } else {
                // root
                compatible = from.getIsDir() && that.__willBeBranch(fromKey);
              }
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
            const to = e.getCurrentTarget();
            // HACK
            if (from.getLabel() === "20181113_Yoon-sun_V4_preview") {
              const mat2ent = qxapp.dev.fake.mat2ent.Data.mat2ent(from.getLabel());
              for (let i=0; i<mat2ent.length; i++) {
                to.getModel().getChildren()
                  .push(mat2ent[i]);
              }
            } else if (from.getModel().getChildren && from.getModel().getChildren().length>0) {
              let children = from.getModel().getChildren();
              for (let i=0; i<children.length; i++) {
                let child = children.toArray()[i];
                if (!child.getChildren) {
                  let data = {
                    key: child.getKey(),
                    label: child.getLabel(),
                    nodeKey: from.getNodeKey(),
                    portKey: from.getPortKey(),
                    isDir: false
                  };
                  this.__createItemAndPush(data, to, fromNodeKey, fromPortKey);
                }
              }
            } else {
              let data = {
                key: from.getModel(),
                label: from.getLabel(),
                nodeKey: from.getNodeKey(),
                portKey: from.getPortKey(),
                isDir: from.getIsDir()
              };
              this.__createItemAndPush(data, to, fromNodeKey, fromPortKey);
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
    if (Object.prototype.hasOwnProperty.call(mapper, "defaultValue")) {
      const defValues = mapper["defaultValue"];
      for (let i=0; i<defValues.length; i++) {
        const defValue = defValues[i];
        for (const defValueId in defValue) {
          let newBranch = {
            key: defValueId,
            label: defValueId.replace("-UUID", ""),
            nodeKey: nodeModel.getKey(),
            portKey: "myPort",
            isDir: true,
            children: []
          };
          let newItemBranch = qx.data.marshal.Json.createModel(newBranch, true);
          const itemProps = qxapp.data.Store.getInstance().getItem(null, Object.keys(nodeModel.getInputsDefault())[0], defValueId);
          if (itemProps) {
            let form = new qxapp.component.form.Auto(itemProps, this.getNodeModel());
            let propsWidget = new qxapp.component.form.renderer.PropForm(form);
            newItemBranch["propsWidget"] = propsWidget;
          }
          data.children.push(newItemBranch);
          const values = defValue[defValueId];
          for (let j=0; j<values.length; j++) {
            let newLeaf = {
              key: values[j],
              label: values[j],
              nodeKey: nodeModel.getKey(),
              portKey: "myPort",
              isDir: true
            };
            let newItemLeaf = qx.data.marshal.Json.createModel(newLeaf, true);
            newItemBranch.getChildren().push(newItemLeaf);
          }
        }
      }
    }
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

    __createItemAndPush: function(data, to, fromNodeKey, fromPortKey) {
      const willBeBranch = this.__willBeBranch(fromNodeKey);
      if (willBeBranch) {
        data["children"] = [];
      }
      let newItem = qx.data.marshal.Json.createModel(data, true);
      to.getModel().getChildren()
        .push(newItem);
      if (willBeBranch) {
        // Hmmmm not sure about the double getKey :(
        const itemProps = qxapp.data.Store.getInstance().getItem(null, fromPortKey, newItem.getKey().getKey());
        if (itemProps) {
          let form = new qxapp.component.form.Auto(itemProps, this.getNodeModel());
          let propsWidget = new qxapp.component.form.renderer.PropForm(form);
          newItem["propsWidget"] = propsWidget;
        }
      }
    },

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
