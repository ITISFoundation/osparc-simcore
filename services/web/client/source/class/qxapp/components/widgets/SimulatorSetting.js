qx.Class.define("qxapp.components.widgets.SimulatorSetting", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let simulatorSettingLayout = new qx.ui.layout.HBox(10);
    this._setLayout(simulatorSettingLayout);

    let collapsableVBox1 = new qxapp.components.widgets.CollapsableVBox("Inputs");
    let componentsBox = this.__componentsBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: 250
    });
    collapsableVBox1.addContentWidget(componentsBox, {
      flex: 1
    });
    this._add(collapsableVBox1);

    let collapsableVBox2 = new qxapp.components.widgets.CollapsableVBox("Settings");
    let settingsBox = this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: 250
    });
    collapsableVBox2.addContentWidget(settingsBox, {
      flex: 1
    });
    this._add(collapsableVBox2);

    let contentBox = this.__contentBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      width: 250
    });
    this._add(contentBox);

    let logo = new qx.ui.basic.Image("qxapp/modelerMockup.png").set({
      maxHeight: 438,
      maxWidth: 386,
      scale: true,
      alignX: "center",
      alignY: "middle"
    });
    this._add(logo, {
      flex: 1
    });
  },

  properties: {
    node: {
      check: "qxapp.components.workbench.NodeBase",
      apply: "__applyNode"
    }
  },

  events: {},

  members: {
    __components: null,
    __componentsBox: null,
    __defaultSettings: null,
    __databaseSettings: null,
    __settingsBox: null,
    __contentBox: null,
    __settingsFolder: null,

    __applyNode: function(node, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__componentsBox.removeAll();
      this.__contentBox.removeAll();

      // default settings
      {
        let tree = new qx.ui.tree.Tree().set({
          selectionMode: "single",
          openMode: "none"
        });
        let root = new qx.ui.tree.TreeFolder("Default Settings").set({
          open: true
        });
        tree.setRoot(root);
        this.__settingsBox.add(tree, {
          flex: 1
        });
        const metaData = this.getNode().getMetaData();
        const nodeImageId = metaData.key + "-" + metaData.version;
        this.__populateList(root, nodeImageId, true);
      }

      // modeler (and DB)
      for (const portKey in node.getInputPorts()) {
        const port = node.getInputPort(portKey);
        const portType = port.portType;
        if (portType.includes("data:application/s4l-api")) {
          const apiType = portType.split("/").pop();
          if (apiType !== "settings") {
            let tree = new qx.ui.tree.Tree().set({
              selectionMode: "single",
              openMode: "none"
            });
            let root = new qx.ui.tree.TreeFolder(portKey).set({
              open: true
            });
            tree.setRoot(root);
            switch (apiType) {
              case "modeler":
                tree.setSelectionMode("multi");
                this.__components = tree;
                this.__componentsBox.add(tree, {
                  flex: 1
                });
                this.__populateList(root, portType, false);
                break;
              case "materialDB":
                this.__databaseSettings = tree;
                this.__settingsBox.add(tree, {
                  flex: 1
                });
                this.__populateList(root, portType, true);
                break;
            }
          }
        }
      }

      // Settings
      {
        let tree = new qx.ui.tree.Tree().set({
          selectionMode: "single",
          openMode: "none"
        });
        const settingName = node.getMetaData().name;
        let root = this.__settingsFolder = new qx.ui.tree.TreeFolder(settingName).set({
          open: true,
          droppable: true
        });
        tree.setRoot(root);
        this.__contentBox.add(tree, {
          flex: 1
        });

        root.addListener("dragover", e => {
          let compatible = false;
          const dataType = "setting-container";
          if (e.supportsType(dataType)) {
            compatible = this.__isCompatible();
          }
          if (!compatible) {
            e.preventDefault();
          }
        }, this);

        root.addListener("drop", e => {
          const eDataType = "setting-container";
          if (e.supportsType(eDataType)) {
            const eData = e.getData(eDataType);
            let conceptSetting = new qx.ui.tree.TreeFolder(eData.name).set({
              open: true,
              droppable: true
            });
            conceptSetting.data = eData;
            root.add(conceptSetting);

            conceptSetting.addListener("dragover", ev => {
              let compatible = false;
              const evDataType = "setting-component";
              if (ev.supportsType(evDataType)) {
                compatible = this.__isCompatible();
              }
              if (!compatible) {
                ev.preventDefault();
              }
            }, this);

            conceptSetting.addListener("drop", ev => {
              const evDataType = "setting-component";
              if (ev.supportsType(evDataType)) {
                const evData = ev.getData(evDataType);
                const componentName = evData.name;
                let component = new qx.ui.tree.TreeFile(componentName);
                component.data = evData;
                conceptSetting.add(component);
                conceptSetting.setOpen(true);
              }
            }, this);
          }
        }, this);
      }
    },

    __isCompatible: function() {
      return true;
    },

    __populateList: function(root, imageId, isSetting = false) {
      let store = qxapp.data.Store.getInstance();
      const list = store.getList(imageId);
      for (let i=0; i<list.length; i++) {
        const label = list[i].name;
        let treeItem = isSetting ? new qx.ui.tree.TreeFolder(label) : new qx.ui.tree.TreeFile(label);
        treeItem.setDraggable(true);
        root.add(treeItem);

        treeItem.addListener("dragstart", e => {
          e.addAction("copy");

          const dataType = isSetting ? "setting-container" : "setting-component";
          e.addType(dataType);
          e.addData(dataType, list[i]);
        }, this);
      }
    },

    listClicked: function() {
      const compIndex = this._indexOf(this.__componentsBox);
      if (compIndex > -1) {
        this._remove(this.__componentsBox);
      } else {
        this._addAt(this.__componentsBox, 0);
      }
    },

    addClicked: function() {
      const compIndex = this._indexOf(this.__componentsBox);
      const settIndex = this._indexOf(this.__settingsBox);
      if (settIndex > -1) {
        this._remove(this.__settingsBox);
      } else {
        this._addAt(this.__settingsBox, compIndex+1);
      }
    }
  }
});
