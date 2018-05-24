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


    let progressBox = new qx.ui.container.Composite(new qx.ui.layout.Basic());
    progressBox.setMinWidth(160);

    this.__progressBar = new qx.ui.indicator.ProgressBar();
    this.__progressBar.setWidth(160);
    progressBox.add(this.__progressBar, {
      top: 0,
      left: 0
    });

    this.__progressLabel = new qx.ui.basic.Label("0%");
    progressBox.add(this.__progressLabel, {
      top: 3,
      left: 70
    });

    this.add(progressBox);


    this.__inputPorts = [];
    this.__outputPorts = [];
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
    }
  },

  events: {
    "LinkDragStart": "qx.event.type.Data",
    "LinkDragOver": "qx.event.type.Data",
    "LinkDrop": "qx.event.type.Data",
    "LinkDragEnd": "qx.event.type.Data",
    "NodeMoving":  "qx.event.type.Event"
  },

  members: {
    __inputPorts: null,
    __outputPorts: null,
    __inputPortsUI: null,
    __outputPortsUI: null,
    __progressLabel: null,
    __progressBar: null,

    getInputPorts: function() {
      return this.__inputPorts;
    },

    getOutputPorts: function() {
      return this.__outputPorts;
    },

    getSetting: function(settingId) {
      let settings = this.getMetadata().settings;
      for (let i = 0; i < settings.length; i++) {
        if (settings[i].key === settingId) {
          return settings[i];
        }
      }
      return null;
    },

    // override qx.ui.window.Window "move" event listener
    _onMovePointerMove: function(e) {
      this.base(arguments, e);
      if (e.getPropagationStopped() === true) {
        this.fireEvent("NodeMoving");
      }
    },

    getCurrentBounds: function() {
      let bounds = this.getBounds();
      let cel = this.getContentElement();
      if (cel) {
        let domeEle = cel.getDomElement();
        if (domeEle) {
          bounds.left = parseInt(domeEle.style.left);
          bounds.top = parseInt(domeEle.style.top);
        }
      }
      // NavigationBar height must be subtracted
      // bounds.left = this.getContentLocation().left;
      // bounds.top = this.getContentLocation().top;
      return bounds;
    },

    __applyMetadata: function(metadata, old) {
      if (metadata != undefined) {
        this.set({
          serviceName: metadata.label,
          nodeImageId: metadata.key
        });
        this.addInputs(metadata.inputs);
        this.addOutputs(metadata.outputs);
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    __addInputPort: function(input) {
      this.getInputPorts().push(input);
      this.__inputPortsUI.add(input.ui);
    },

    __removeInputPort: function(port) {
      var index = this.getInputPorts().indexOf(port);
      if (index > -1) {
        this.__inputPortsUI.remove(port.ui);
        this.getInputPorts().splice(index, 1);
      }
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

    getPortIndex: function(portId) {
      const nInPorts = this.getInputPorts().length;
      for (let i = 0; i < nInPorts; i++) {
        if (this.getInputPorts()[i].portId === portId) {
          return i;
        }
      }
      const nOutPorts = this.getOutputPorts().length;
      for (let i = 0; i < nOutPorts; i++) {
        if (this.getOutputPorts()[i].portId === portId) {
          return i;
        }
      }
      return 0;
    },

    addInput: function(inputData) {
      let label = this.__createPort(true, inputData);
      this.__addInputPort(label);
    },

    addInputs: function(inputs) {
      for (let inputData of inputs) {
        this.addInput(inputData);
      }
    },

    removeInput: function(port) {
      this.__removeInputPort(port);
    },

    addOutput: function(outputData) {
      let label = this.__createPort(false, outputData);
      this.__addOutputPort(label);
    },

    addOutputs: function(outputs) {
      for (let outputData of outputs) {
        this.addOutput(outputData);
      }
    },

    __createPort: function(isInput, portData) {
      let label = {};
      label.portId = portData.key;
      label.isInput = isInput;
      label.portType = portData.type;

      label.ui = new qx.ui.basic.Label(portData.label).set({
        height: 16,
        draggable: true,
        droppable: true
      });
      label.ui.addListener("dragstart", function(e) {
        this.fireDataEvent("LinkDragStart", [e, this.getNodeId(), label.portId]);
      }, this);
      label.ui.addListener("dragover", function(e) {
        this.fireDataEvent("LinkDragOver", [e, this.getNodeId(), label.portId]);
      }, this);
      label.ui.addListener("drop", function(e) {
        this.fireDataEvent("LinkDrop", [e, this.getNodeId(), label.portId]);
      }, this);
      label.ui.addListener("dragend", function(e) {
        this.fireDataEvent("LinkDragEnd", [e, this.getNodeId(), label.portId]);
      }, this);
      return label;
    },

    setProgress: function(progress) {
      this.__progressLabel.setValue(progress + "%");
      this.__progressBar.setValue(progress);
    }
  }
});
