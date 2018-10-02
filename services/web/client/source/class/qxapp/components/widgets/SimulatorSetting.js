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
    __componentsBox: null,
    __settingsBox: null,
    __settingsTree: null,
    __settingProps: null,
    __contentBox: null,
    __contentProps: null,

    __applyNode: function(node, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__componentsBox.removeAll();
      this.__contentBox.removeAll();

      // default settings
      let inputSettingsTree = this.__settingsTree = this.__createTree();
      let defaultSettingsFolder = new qx.ui.tree.TreeFolder("Default Settings").set({
        open: true
      });
      inputSettingsTree.getRoot().add(defaultSettingsFolder);
      inputSettingsTree.addListener("changeSelection", e => {
        let data = e.getData()[0];
        this.__showPropertiesInSettings(data);
      }, this);
      this.__settingsBox.add(inputSettingsTree, {
        flex: 1
      });
      const metaData = this.getNode().getMetaData();
      const nodeImageId = metaData.key + "-" + metaData.version;
      this.__populateList(defaultSettingsFolder, nodeImageId, true);

      // modeler (and DB)
      for (const portKey in node.getInputPorts()) {
        const port = node.getInputPort(portKey);
        const portType = port.portType;
        if (portType.includes("data:application/s4l-api")) {
          const apiType = portType.split("/").pop();
          if (apiType !== "settings") {
            switch (apiType) {
              case "modeler": {
                let inputModelerTree = this.__modelerTree = this.__createTree();
                let modelerFolder = new qx.ui.tree.TreeFolder(portKey).set({
                  open: true
                });
                inputModelerTree.getRoot().add(modelerFolder);
                inputModelerTree.setSelectionMode("multi");
                this.__componentsBox.add(inputModelerTree, {
                  flex: 1
                });
                this.__populateList(modelerFolder, portType, false);
              }
                break;
              case "materialDB": {
                let matFolder = new qx.ui.tree.TreeFolder(portKey).set({
                  open: true
                });
                this.__settingsTree.getRoot().add(matFolder);
                this.__populateList(matFolder, portType, true);
              }
                break;
            }
          }
        }
      }

      // Settings
      {
        let conceptSettingsTree = this.__createTree();
        const settingName = node.getMetaData().name;
        let conceptSettingsFolder = new qx.ui.tree.TreeFolder(settingName).set({
          open: true,
          droppable: true
        });
        conceptSettingsTree.getRoot().add(conceptSettingsFolder);
        conceptSettingsTree.addListener("changeSelection", e => {
          let data = e.getData()[0];
          this.__showPropertiesInContent(data);
        }, this);
        this.__contentBox.add(conceptSettingsTree, {
          flex: 1
        });

        conceptSettingsFolder.addListener("dragover", e => {
          let compatible = false;
          const dataType = "setting-container";
          if (e.supportsType(dataType)) {
            compatible = this.__isCompatible();
          }
          if (!compatible) {
            e.preventDefault();
          }
        }, this);

        conceptSettingsFolder.addListener("drop", e => {
          const eDataType = "setting-container";
          if (e.supportsType(eDataType)) {
            const eData = e.getData(eDataType);
            let conceptSetting = new qx.ui.tree.TreeFolder(eData.name).set({
              open: true,
              droppable: true
            });
            conceptSetting.data = eData;
            conceptSetting.form = this.__createForm(eData.properties);
            conceptSettingsFolder.add(conceptSetting);

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

      this.__settingProps = new qx.ui.core.Widget();
      this.__settingsBox.add(this.__settingProps);
      this.__contentProps = new qx.ui.core.Widget();
      this.__contentBox.add(this.__contentProps);
    },

    __isCompatible: function() {
      return true;
    },

    __createTree: function(folderLabel) {
      let tree = new qx.ui.tree.Tree().set({
        selectionMode: "single",
        openMode: "none"
      });

      let root = new qx.ui.tree.TreeFolder("root");
      root.setOpen(true);
      tree.setRoot(root);
      tree.setHideRoot(true);

      return tree;
    },

    __populateList: function(root, imageId, isSetting = false) {
      let store = qxapp.data.Store.getInstance();
      const list = store.getList(imageId);
      for (let i=0; i<list.length; i++) {
        const label = list[i].name;
        let treeItem = isSetting ? new qx.ui.tree.TreeFolder(label) : new qx.ui.tree.TreeFile(label);
        treeItem.setDraggable(true);
        treeItem.form = this.__createForm(list[i].properties);
        root.add(treeItem);

        treeItem.addListener("dragstart", e => {
          e.addAction("copy");

          const dataType = isSetting ? "setting-container" : "setting-component";
          e.addType(dataType);
          e.addData(dataType, list[i]);
        }, this);
      }
    },

    __createForm: function(inputs) {
      if (inputs === null) {
        return null;
      }
      let form = new qxapp.components.form.Auto(inputs);
      let propForm = new qxapp.components.form.renderer.PropForm(form);
      return propForm;
    },

    __showPropertiesInSettings: function(data) {
      this.__settingsBox.remove(this.__settingProps);
      if ("form" in data) {
        this.__settingProps = data.form;
        this.__settingProps.enableAllProps(false);
      } else {
        this.__settingProps = new qx.ui.core.Widget();
      }
      this.__settingsBox.add(this.__settingProps);
    },

    __showPropertiesInContent: function(data) {
      this.__contentBox.remove(this.__contentProps);
      if ("form" in data) {
        this.__contentProps = data.form;
      } else {
        this.__contentProps = new qx.ui.core.Widget();
      }
      this.__contentBox.add(this.__contentProps);
    }
  }
});
