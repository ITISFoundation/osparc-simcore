/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true, "allow": ["__widgetChildren"] }] */

qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base();

    this.set({
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      minWidth: 180
    });

    let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
    this.setLayout(nodeLayout);

    let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
    this.add(inputsOutputsLayout, {
      flex: 1
    });

    let inputsBox = new qx.ui.layout.VBox(5);
    inputsBox.setAlignX("left");
    this.__inputPortsUI = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this.__inputPortsUI, {
      width: "50%"
    });

    let outputsBox = new qx.ui.layout.VBox(5);
    outputsBox.setAlignX("right");
    this.__outputPortsUI = new qx.ui.container.Composite(outputsBox);
    inputsOutputsLayout.add(this.__outputPortsUI, {
      width: "50%"
    });

    let progressBox = new qx.ui.layout.HBox(5);
    progressBox.setAlignX("center");
    let progressLayout = new qx.ui.container.Composite(progressBox);
    this.__progressLabel = new qx.ui.basic.Label("0%");
    progressLayout.add(this.__progressLabel);
    this.add(progressLayout);

    this.setNodeId(qxapp.utils.Utils.uuidv4());
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    },

    nodeImageId: {
      check: "String",
      nullable: false
    },

    metadata: {
      apply : "__applyMetadata"
    },

    inputPorts: {
      check: "Array",
      init: [],
      nullable: false
    },

    outputPorts: {
      check: "Array",
      init: [],
      nullable: false
    },

    inputLinkIDs: {
      check: "Array",
      init: [],
      nullable: false
    },

    outputLinkIDs: {
      check: "Array",
      init: [],
      nullable: false
    }
  },

  events: {
    "StartTempConn": "qx.event.type.Data",
    "EndTempConn": "qx.event.type.Data"
  },

  members: {
    __inputPortsUI: null,
    __outputPortsUI: null,
    __progressLabel: null,

    __applyMetadata: function(value, old) {
      if (value != undefined) {
        this.setMetadata(value);
        this.setServiceName(this.getMetadata().name);
        this.setNodeImageId(this.getMetadata().id);
        this.setInputs(this.getMetadata().inputs);
        this.setOutputs(this.getMetadata().outputs);
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    __addInputPort: function(input) {
      this.getInputPorts().push(input);
      this.__inputPortsUI.add(input.ui);
    },

    __addOutputPort: function(input) {
      this.getOutputPorts().push(input);
      this.__outputPortsUI.add(input.ui);
    },

    getPort: function(portId) {
      const nInPorts = this.getInputPorts().length;
      for (let i = 0; i < nInPorts; i++) {
        if (this.getInputPorts()[i].portId === portId) {
          return this.getInputPorts()[i];
        }
      }
      const nOutPorts = this.getOutputPorts().length;
      for (let i = 0; i < nOutPorts; i++) {
        if (this.getOutputPorts()[i].portId === portId) {
          return this.getOutputPorts()[i];
        }
      }
      return null;
    },

    setInputs: function(inputs) {
      for (let inputData of inputs) {
        let label = this.__createPort(true, inputData);
        this.__addInputPort(label);
      }
    },

    setOutputs: function(outputs) {
      for (let outputData of outputs) {
        let label = this.__createPort(false, outputData);
        this.__addOutputPort(label);
      }
    },

    __createPort: function(isInput, portData) {
      let label = {};
      if ("uuid" in portData && portData.uuid !== undefined) {
        label.portId = portData.uuid;
      } else {
        label.portId = qxapp.utils.Utils.uuidv4();
      }
      label.isInput = isInput;
      label.portType = portData.portType;

      label.ui = new qx.ui.basic.Label(portData.name);
      label.ui.setDraggable(true);
      label.ui.setDroppable(true);
      label.ui.addListener("dragstart", function(e) {
        this.__handleDragStart(e, this.getNodeId(), label.portId);
      }, this);
      label.ui.addListener("droprequest", function(e) {
        this.__handleDropRequest(e, this.getNodeId(), label.portId);
      }, this);
      label.ui.addListener("dragover", function(e) {
        this.__handleDragOver(e, this.getNodeId(), label.portId);
      }, this);
      label.ui.addListener("drop", function(e) {
        this.__handleDrop(e, this.getNodeId(), label.portId);
      }, this);
      return label;
    },

    addInputLinkID: function(linkID) {
      this.getInputLinkIDs().push(linkID);
    },

    addOutputLinkID: function(linkID) {
      this.getOutputLinkIDs().push(linkID);
    },

    __handleDragStart: function(e, nodeId, portId) {
      console.log("dragstart", e, nodeId, portId);

      // Register supported types
      e.addType("osparc-metadata");

      // Register supported actions
      e.addAction("move");

      this.fireDataEvent("StartTempConn", [nodeId, portId]);
    },

    __handleDropRequest: function(e, nodeId, portId) {
      console.log("droprequest", e, nodeId, portId);
      /*
      let type = e.getCurrentType();
      let action = e.getCurrentAction();
      let dragTarget = e.getDragTarget();
      let result = null;
      switch (type) {
        case "osparc-metadata":
          if (action === "move") {
            result = dragTarget.portType;
            e.addData("osparc-metadata", result);
          }
      }
      */
    },

    __handleDragOver: function(e, nodeId, portId) {
      console.log("dragover", e, nodeId, portId);
    },

    __handleDrop: function(e, nodeId, portId) {
      console.log("drop", e, nodeId, portId);
      if (e.supportsType("osparc-metadata")) {
        this.fireDataEvent("EndTempConn", [nodeId, portId]);
      }
    }
  }
});
