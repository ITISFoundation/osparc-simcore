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

    __arePortsCompatible: function(port1, port2) {
      return qxapp.data.Store.getInstance().arePortsCompatible(port1, port2);
    },

    __createDragDropMechanism: function(nodeBase) {
      const evType = "pointermove";
      nodeBase.addListener("LinkDragStart", function(e) {
        let data = e.getData();
        let event = data.event;
        let dragNodeId = data.nodeId;
        let dragIsInput = data.isInput;

        // Register supported actions
        event.addAction("move");

        // Register supported types
        event.addType("osparc-metaData");
        let dragData = {
          dragNodeId: dragNodeId,
          dragIsInput: dragIsInput
        };
        event.addData("osparc-metaData", dragData);

        this.__tempLinkNodeId = dragData.dragNodeId;
        this.__tempLinkIsInput = dragData.dragIsInput;
        qx.bom.Element.addListener(
          this.__desktop,
          evType,
          this.__startTempLink,
          this
        );
      }, this);

      nodeBase.addListener("LinkDragOver", function(e) {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        let compatible = false;
        if (event.supportsType("osparc-metaData")) {
          const dragNodeId = event.getData("osparc-metaData").dragNodeId;
          const dragIsInput = event.getData("osparc-metaData").dragIsInput;
          const dragNode = this.__getNodeUI(dragNodeId);
          const dropNode = this.__getNodeUI(dropNodeId);
          const dragPortTarget = dragIsInput ? dragNode.getInputPort() : dragNode.getOutputPort();
          const dropPortTarget = dropIsInput ? dropNode.getInputPort() : dropNode.getOutputPort();
          compatible = this.__arePortsCompatible(dragPortTarget, dropPortTarget);
        }

        if (!compatible) {
          event.preventDefault();
        }
      }, this);

      nodeBase.addListener("LinkDrop", function(e) {
        let data = e.getData();
        let event = data.event;
        let dropNodeId = data.nodeId;
        let dropIsInput = data.isInput;

        if (event.supportsType("osparc-metaData")) {
          let dragNodeId = event.getData("osparc-metaData").dragNodeId;
          let dragIsInput = event.getData("osparc-metaData").dragIsInput;

          let nodeAId = dropIsInput ? dragNodeId : dropNodeId;
          let nodeBId = dragIsInput ? dragNodeId : dropNodeId;

          this.__createLinkBetweenNodes({
            nodeUuid: nodeAId
          }, {
            nodeUuid: nodeBId
          });
          this.__removeTempLink();
          qx.bom.Element.removeListener(
            this.__desktop,
            evType,
            this.__startTempLink,
            this
          );
        }
      }, this);
    },

    __createInputNodeUI: function(inputNodeModel) {
      let nodePorts = new qxapp.components.widgets.NodePorts(inputNodeModel);
      nodePorts.populateNodeLayout();
      this.__createDragDropMechanism(nodePorts);
      return nodePorts;
    },

    __createInputNodeUIs: function(model) {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length-1);
      }

      const inputNodes = model.getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNodeModel = this.getWorkbenchModel().getNodeModel(inputNodes[i]);
        let inputLabel = this.__createInputNodeUI(inputNodeModel);
        this.__nodesUI.push(inputLabel);
        this.__inputNodesLayout.add(inputLabel, {
          flex: 1
        });
      }
    },

    __applyNode: function(nodeModel, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(nodeModel.getPropsWidget());

      this.__createInputNodeUIs(nodeModel);

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
