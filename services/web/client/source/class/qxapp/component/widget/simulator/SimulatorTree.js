/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * VirtualTree used for showing SimulatorTree from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function(node) {
    this.base(arguments, null, "label", "children");

    this.set({
      node: node
    });

    this.set({
      openMode: "none"
    });
    this.setDelegate({
      createItem: () => new qxapp.component.widget.simulator.SimulatorTreeItem(),
      configureItem: item => {
        item.set({
          droppable: true
        });
        item.addListener("dragover", e => {
          item.set({
            droppable: item.getIsDir()
          });
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const fromNodeKey = from.getNodeKey();
            const fromItemKey = from.getModel().getKey();
            const to = e.getCurrentTarget();
            if (to.getIsDir()) {
              const simulator = this.getNode();
              const settingKey = to.getKey();
              simulator.checkCompatibility(settingKey, fromNodeKey, fromItemKey, e);
            } else {
              e.preventDefault();
            }
          } else {
            e.preventDefault();
          }
        });
        item.addListener("drop", e => {
          if (e.supportsType("osparc-mapping")) {
            const from = e.getRelatedTarget();
            const fromNodeKey = from.getNodeKey();
            const fromPortKey = from.getPortKey();
            const to = e.getCurrentTarget();
            if (from.getLabel() === "20181113_Yoon-sun_V4_preview") {
              // HACK
              const mat2ent = qxapp.dev.fake.mat2ent.Data.mat2ent(from.getLabel());
              for (let i=0; i<mat2ent.length; i++) {
                to.getModel().getChildren()
                  .push(mat2ent[i]);
              }
            } else if (from.getModel().getChildren && from.getModel().getChildren().length>0) {
              // allow folder drag&drop
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
            this.focus();
          }
        });
      },
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        // c.bindProperty("key", "model", null, item, id);
        c.bindProperty("key", "key", null, item, id);
        c.bindProperty("version", "version", null, item, id);
        c.bindProperty("metadata", "metadata", null, item, id);
        c.bindProperty("isDir", "isDir", null, item, id);
        c.bindProperty("isRoot", "isRoot", null, item, id);
        const simulator = this.getNode();
        item.createNode(simulator.getWorkbench());
        if (item.getNode().getInputsMapper()) {
          const mapper = item.getNode().getInputsMapper();
          if (mapper.defaultValue) {
            const defValues = mapper["defaultValue"];
            for (let i=0; i<defValues.length; i++) {
              const defValue = defValues[i];
              for (const defValueId in defValue) {
                let newBranch = {
                  key: defValueId,
                  label: defValueId.replace("-UUID", ""),
                  nodeKey: node.getKey(),
                  portKey: "myPort",
                  isDir: true,
                  children: []
                };
                let newItemBranch = qx.data.marshal.Json.createModel(newBranch, true);
                const itemProps = qxapp.data.Store.getInstance().getItem(null, Object.keys(node.getInputsDefault())[0], defValueId);
                if (itemProps) {
                  const itemNode = item.getNode();
                  const workbench = node.getWorkbench();
                  let form = new qxapp.component.form.Auto(itemProps, itemNode);
                  let propsWidget = new qxapp.component.form.renderer.PropForm(form, workbench, itemNode);
                  newItemBranch["propsWidget"] = propsWidget;
                }
                // data.children.push(newItemBranch);
                item.getChildren().push(newItemBranch);
                const values = defValue[defValueId];
                for (let j=0; j<values.length; j++) {
                  let newLeaf = {
                    key: values[j],
                    label: values[j],
                    nodeKey: node.getKey(),
                    portKey: "myPort",
                    isDir: true
                  };
                  let newItemLeaf = qx.data.marshal.Json.createModel(newLeaf, true);
                  newItemBranch.getChildren().push(newItemLeaf);
                }
              }
            }
          }
        }
      }
    });
    this.addListener("tap", this.__selectionChanged, this);

    this.__populateTree();

    this.__initEvents();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    mapper: {
      nullable: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Data"
  },

  members: {
    __populateTree: function() {
      const store = qxapp.data.Store.getInstance();
      const itemList = store.getItemList(this.getNode().getKey());
      let children = [];
      for (let i=0; i<itemList.length; i++) {
        const metadata = store.getItem(this.getNode().getKey(), itemList[i].key);
        let newEntry = {
          key: itemList[i].key,
          version: itemList[i].version,
          metadata: metadata,
          isDir: false
        };
        if ("inputs" in metadata && "mapper" in metadata.inputs) {
          newEntry.children = [];
          newEntry.isDir = true;
        }
        children.push(newEntry);
      }
      let data = {
        label: this.getNode().getLabel(),
        key: null,
        metadata: null,
        isRoot: true,
        children: children
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.setModel(model);
    },

    __initEvents: function() {
      this.addListener("keypress", function(keyEvent) {
        let treeSelection = this.getSelection();
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
            treeItemRenamer.addListener("labelChanged", e => {
              let newLabel = e.getData()["newLabel"];
              selectedItem.setLabel(newLabel);
            }, this);
            treeItemRenamer.center();
            treeItemRenamer.open();
            break;
          }
          case "Delete": {
            let branches = this.getModel().getChildren();
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

    __selectionChanged: function(e) {
      const selection = e.getTarget();
      if ("getNode" in selection) {
        this.fireDataEvent("selectionChanged", selection.getNode());
      } else {
        this.fireDataEvent("selectionChanged", null);
      }
    },

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
          let form = new qxapp.component.form.Auto(itemProps, this.getNode());
          let propsWidget = new qxapp.component.form.renderer.PropForm(form);
          newItem["propsWidget"] = propsWidget;
        }
      }
    },

    __willBeBranch: function(candidate) {
      let isBranch = false;
      const maps = this.getMapper().maps;
      if (maps.branch) {
        if (maps["branch"] === candidate) {
          isBranch = true;
        }
      }
      const isDefault = candidate === this.getNode().getKey();
      return isDefault || isBranch;
    },

    __willBeLeaf: function(candidate) {
      let isLeave = false;
      const maps = this.getMapper().maps;
      if (maps.leaf) {
        if (maps["leaf"] === candidate) {
          isLeave = true;
        }
      }
      return isLeave;
    }
  }
});
