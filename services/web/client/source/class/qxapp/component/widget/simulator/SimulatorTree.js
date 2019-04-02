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

  construct: function(simulator) {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      node: simulator
    });

    this.setDelegate(this.__getDelegate());

    this.__populateTree();

    this.__initEvents();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Data"
  },

  statics: {
    createRootData: function(label) {
      return {
        label: label,
        key: null,
        metadata: null,
        isRoot: true,
        children: []
      };
    },

    createGlobalSettingData: function(simulatorKey, settingKey, settingVersion) {
      const store = qxapp.data.Store.getInstance();
      const metadata = store.getItem(simulatorKey, settingKey);
      let newEntry = {
        key: settingKey,
        version: settingVersion,
        metadata: metadata,
        isRoot: false,
        isDir: false
      };
      if ("inputs" in metadata && "mapper" in metadata.inputs) {
        newEntry.isDir = true;
        newEntry.children = [];
      }
      return newEntry;
    },

    createConceptSettingData: function(simulatorKey, settingKey, itemKey) {
      const store = qxapp.data.Store.getInstance();
      const metadata = store.getItem(simulatorKey, settingKey, itemKey);
      let newEntry = {
        key: itemKey,
        version: null,
        metadata: metadata,
        isRoot: false,
        isDir: true,
        children: []
      };
      return newEntry;
    }
  },

  members: {
    __getDelegate: function() {
      return {
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
        }
      };
    },

    __populateTree: function() {
      const thisClass = qxapp.component.widget.simulator.SimulatorTree;
      let data = thisClass.createRootData(this.getNode().getLabel());
      let rootModel = qx.data.marshal.Json.createModel(data, true);
      this.setModel(rootModel);

      const simulatorKey = this.getNode().getKey();
      const store = qxapp.data.Store.getInstance();
      const itemList = store.getItemList(simulatorKey);
      for (let i=0; i<itemList.length; i++) {
        const newEntry = thisClass.createGlobalSettingData(simulatorKey, itemList[i].key, itemList[i].version);
        const model = qx.data.marshal.Json.createModel(newEntry, true);
        this.getModel().getChildren()
          .push(model);
      }
    },

    __initEvents: function() {
      this.addListener("tap", this.__selectionChanged, this);

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

    addConceptSetting: function(settingsKey, itemKey) {
      const globalSetting = this.__getGlobalSetting(settingsKey);
      if (globalSetting) {
        const thisClass = qxapp.component.widget.simulator.SimulatorTree;
        const simulatorKey = this.getNode().getKey();
        const newEntry = thisClass.createConceptSettingData(simulatorKey, settingsKey, itemKey);
        const model = qx.data.marshal.Json.createModel(newEntry, true);
        globalSetting.getChildren().push(model);
      }
    },

    __getGlobalSetting: function(settingsKey) {
      const children = this.getModel().getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children.toArray()[i];
        if (child.getKey() === settingsKey) {
          return child;
        }
      }
      return null;
    }
  }
});
