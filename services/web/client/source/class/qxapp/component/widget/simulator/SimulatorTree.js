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

  construct: function(simulator, node) {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      simulator: simulator,
      node: node
    });

    this.setDelegate(this.__getDelegate());

    this.__populateTree();

    this.__initEvents();
  },

  properties: {
    // ToDo: OM Create a non UI Simulator for data handling
    simulator: {
      check: "qx.ui.core.Widget",
      nullable: false
    },

    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Data"
  },

  statics: {
    getMetaData(nodeKey, b, c) {
      const store = qxapp.store.Store.getInstance();
      return store.getItem(nodeKey, b, c);
    },

    createRootData: function(label) {
      return {
        label: label,
        key: null,
        metadata: null,
        isRoot: true,
        children: []
      };
    },

    createGlobalSettingData: function(simulatorKey, globalSettingKey, globalSettingVersion) {
      const thisClass = qxapp.component.widget.simulator.SimulatorTree;
      const metadata = thisClass.getMetaData(simulatorKey, globalSettingKey);
      let newEntry = {
        key: globalSettingKey,
        version: globalSettingVersion,
        metadata: metadata,
        isRoot: false,
        isDir: false
      };
      if ("inputs" in metadata && "mapper" in metadata.inputs) {
        newEntry.isDir = true;
        newEntry.children = [];
        const mapper = metadata.inputs.mapper;
        if ("defaultValue" in mapper) {
          const defaultInputs = mapper.defaultValue;
          for (const defaultInputKey in defaultInputs) {
            const metadata2 = thisClass.getMetaData(simulatorKey, globalSettingKey, defaultInputKey);
            const concSet = thisClass.createConceptSettingData(defaultInputKey, metadata2);
            newEntry.children.push(concSet);
            const values = defaultInputs[defaultInputKey];
            for (let i=0; i<values.length; i++) {
              const comp = thisClass.createComponentData(values[i]);
              concSet.children.push(comp);
            }
          }
        }
      }
      return newEntry;
    },

    createConceptSettingData: function(conceptSettingKey, metadata) {
      let newEntry = {
        key: conceptSettingKey,
        version: null,
        metadata: metadata,
        isRoot: false,
        isDir: true,
        children: []
      };
      return newEntry;
    },

    createComponentData: function(componentKey) {
      let newEntry = {
        key: componentKey,
        label: componentKey.replace("-UUID", ""),
        version: null,
        metadata: null,
        isRoot: false,
        isDir: false
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
                const settingKey = to.getKey();
                let cbk = function(ev, compatible) {
                  if (!compatible) {
                    ev.preventDefault();
                  }
                };
                const simulator = this.getSimulator();
                simulator.checkDragOver(settingKey, fromNodeKey, fromItemKey, cbk);
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
              const fromItemKey = from.getModel().getKey();
              const to = e.getCurrentTarget();
              if (to.getIsDir()) {
                const settingKey = to.getKey();
                let cbk = function(isBranch) {
                  const thisClass = qxapp.component.widget.simulator.SimulatorTree;
                  let data = {};
                  if (isBranch) {
                    const metadata = thisClass.getMetaData(fromNodeKey, fromItemKey);
                    data = thisClass.createConceptSettingData(fromItemKey, metadata);
                  } else {
                    data = thisClass.createComponentData(fromItemKey);
                  }
                  let newItem = qx.data.marshal.Json.createModel(data, true);
                  to.getModel().getChildren()
                    .push(newItem);
                  to.setOpen(true);
                };
                const simulator = this.getSimulator();
                simulator.checkDrop(settingKey, fromNodeKey, fromItemKey, cbk, e);
              }
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
          const node = this.getNode();
          item.createNode(node.getWorkbench());
        }
      };
    },

    __populateTree: function() {
      const thisClass = qxapp.component.widget.simulator.SimulatorTree;
      let data = thisClass.createRootData(this.getNode().getLabel());
      let rootModel = qx.data.marshal.Json.createModel(data, true);
      this.setModel(rootModel);

      const simulatorKey = this.getNode().getKey();
      const store = qxapp.store.Store.getInstance();
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
        let selectedItem = this.__getSelectedEntryModel();
        if (!selectedItem) {
          return;
        }
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

    __getSelectedEntryModel: function() {
      let treeSelection = this.getSelection();
      if (treeSelection.length < 1) {
        return null;
      }
      return treeSelection.toArray()[0];
    },

    __selectionChanged: function(e) {
      const selection = e.getTarget();
      if ("getNode" in selection) {
        this.fireDataEvent("selectionChanged", selection.getNode());
      } else {
        this.fireDataEvent("selectionChanged", null);
      }
    },

    addConceptSetting: function(globalSettingKey, conceptSettingKey) {
      const globalSetting = this.__getGlobalSettingModel(globalSettingKey);
      if (globalSetting) {
        const thisClass = qxapp.component.widget.simulator.SimulatorTree;
        const simulatorKey = this.getNode().getKey();
        const metadata = thisClass.getMetaData(simulatorKey, globalSettingKey, conceptSettingKey);
        const newEntry = thisClass.createConceptSettingData(conceptSettingKey, metadata);
        const model = qx.data.marshal.Json.createModel(newEntry, true);
        globalSetting.getChildren().push(model);
        return model;
      }
      return null;
    },

    __getGlobalSettingModel: function(settingsKey) {
      const children = this.getModel().getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children.toArray()[i];
        if (child.getKey() === settingsKey) {
          return child;
        }
      }
      return null;
    },

    __getGlobalSetting: function(settingsKey) {
      const children = this.getModel().getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children.toArray()[i];
        if (child.getKey() === settingsKey) {
          return children[i];
        }
      }
      return null;
    }
  }
});
