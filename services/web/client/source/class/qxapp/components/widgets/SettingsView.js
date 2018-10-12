const PORT_INPUTS_WIDTH = 300;

qx.Class.define("qxapp.components.widgets.SettingsView", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let hBox = new qx.ui.layout.HBox(10);
    this.set({
      layout: hBox,
      padding: 10
    });

    let inputNodesLayout = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    inputNodesLayout.set({
      width: PORT_INPUTS_WIDTH,
      maxWidth: PORT_INPUTS_WIDTH,
      allowGrowX: false
    });
    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label(this.tr("Inputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);
    this.add(inputNodesLayout);


    let mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    mainLayout.set({
      alignX: "center",
      padding: 70
    });
    this.add(mainLayout, {
      flex: 1
    });

    this.__nodesUI = [];

    this.__initTitle();
    this.__initSettings();
    this.__initButtons();
  },

  events: {
    "ShowViewer": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    },

    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      apply: "__applyNode"
    }
  },

  members: {
    __settingsBox: null,
    __inputNodesLayout: null,
    __mainLayout: null,
    __nodesUI: null,
    __startNode: null,
    __openFoler: null,

    __initTitle: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let titleBox = new qx.ui.container.Composite(box);

      let settLabel = new qx.ui.basic.Label(this.tr("Settings"));
      settLabel.set({
        alignX: "center",
        alignY: "middle"
      });

      titleBox.add(settLabel, {
        width: "75%"
      });
      this.__mainLayout.add(titleBox);
    },

    __initSettings: function() {
      this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.Grow());
      this.__mainLayout.add(this.__settingsBox);
    },

    __initButtons: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let buttonsBox = new qx.ui.container.Composite(box);

      let startNode = this.__startNode = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/play/32"
      });

      let openFolder = this.__openFoler = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/folder-open/32"
      });
      openFolder.addListener("execute", function() {
        let fileManager = new qxapp.components.widgets.FileManager(this.getNodeModel()).set({
          width: 600,
          height: 400
        });

        let win = new qx.ui.window.Window(this.getNodeModel().getLabel()).set({
          layout: new qx.ui.layout.Canvas(),
          contentPadding: 0,
          showMinimize: false
        });
        win.add(fileManager, {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        });

        win.center();
        win.open();
      }, this);

      buttonsBox.add(startNode);
      buttonsBox.add(openFolder);
      this.__mainLayout.add(buttonsBox);
    },

    __getNodeUI: function(id) {
      for (let i = 0; i < this.__nodesUI.length; i++) {
        if (this.__nodesUI[i].getNodeUI() === id) {
          return this.__nodesUI[i];
        }
      }
      return null;
    },

    __arePortsCompatible: function(node1, port1, node2, port2) {
      return qxapp.data.Store.getInstance().arePortsCompatible(node1, port1, node2, port2);
    },

    __createDragDropMechanism: function(portUI) {
      portUI.addListener("PortDragStart", function(e) {
        let data = e.getData();
        let event = data.event;
        let dragNodeId = data.nodeId;
        let dragPortId = data.portId;

        // Register supported actions
        event.addAction("copy");

        // Register supported types
        event.addType("osparc-port-link");
        let dragData = {
          dragNodeId: dragNodeId,
          dragPortId: dragPortId
        };
        event.addData("osparc-port-link", dragData);
      }, this);

      portUI.addListener("PortDragOver", function(e) {
        let data = e.getData();
        let event = data.event;
        // let dropNodeId = data.nodeId;
        let dropNodeId = this.getNodeModel().getNodeId();
        let dropPortId = data.portId;

        let compatible = false;
        if (event.supportsType("osparc-port-link")) {
          const dragNodeId = event.getData("osparc-port-link").dragNodeId;
          const dragPortId = event.getData("osparc-port-link").dragPortId;
          compatible = this.__arePortsCompatible(dragNodeId, dragPortId, dropNodeId, dropPortId);
        }

        if (!compatible) {
          event.preventDefault();
        }
      }, this);

      portUI.addListener("PortDrop", function(e) {
        let data = e.getData();
        let event = data.event;
        // let dropNodeId = data.nodeId;
        let dropNodeId = this.getNodeModel().getNodeId();
        let dropPortId = data.portId;

        if (event.supportsType("osparc-port-link")) {
          let dragNodeId = event.getData("osparc-port-link").dragNodeId;
          let dragPortId = event.getData("osparc-port-link").dragPortId;
          console.log("Create data link", dragNodeId, dragPortId, dropNodeId, dropPortId);
        }
      }, this);
    },

    __createInputPortsUI: function(inputNodeModel) {
      let nodePorts = new qxapp.components.widgets.NodePorts(inputNodeModel);
      nodePorts.populateNodeLayout();
      this.__createDragDropMechanism(nodePorts);
      this.__inputNodesLayout.add(nodePorts, {
        flex: 1
      });
      return nodePorts;
    },

    __createInputPortsUIs: function(nodeModel) {
      const inputNodes = nodeModel.getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNodeModel = this.getWorkbenchModel().getNodeModel(inputNodes[i]);
        if (inputNodeModel.isContainer()) {
          for (const exposedInnerNodeId in inputNodeModel.getExposedInnerNodes()) {
            const exposedInnerNode = inputNodeModel.getExposedInnerNodes()[exposedInnerNodeId];
            this.__createInputPortsUI(exposedInnerNode);
          }
        } else {
          let inputLabel = this.__createInputPortsUI(inputNodeModel);
          this.__nodesUI.push(inputLabel);
        }
      }
    },

    __clearInputPortsUIs: function() {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length-1);
      }
    },

    __applyNode: function(nodeModel, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(nodeModel.getPropsWidget());
      this.__createDragDropMechanism(nodeModel.getPropsWidget());

      this.__clearInputPortsUIs();
      this.__createInputPortsUIs(nodeModel);

      let viewerButton = nodeModel.getViewerButton();
      if (viewerButton) {
        nodeModel.addListenerOnce("ShowViewer", function(e) {
          const data = e.getData();
          this.fireDataEvent("ShowViewer", data);
        }, this);
        this.__startNode = viewerButton;
      }
    }
  }
});
