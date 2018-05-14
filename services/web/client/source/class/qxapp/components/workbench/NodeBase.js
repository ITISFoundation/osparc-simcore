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
    this.__inputPorts = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this.__inputPorts, {
      width: "50%"
    });

    let outputsBox = new qx.ui.layout.VBox(5);
    outputsBox.setAlignX("right");
    this.__outputPorts = new qx.ui.container.Composite(outputsBox);
    inputsOutputsLayout.add(this.__outputPorts, {
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

  members: {
    __inputPorts: null,
    __outputPorts: null,
    __progressLabel: null,

    __applyMetadata: function(value, old) {
      if (value != undefined) {
        this.setMetadata(value);
        this.setServiceName(this.getMetadata().name);
        this.setNodeImageId(this.getMetadata().id);
        this.setInputs(this.getMetadata().input);
        this.setOutputs(this.getMetadata().output);
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    setInputs: function(inputs) {
      inputs.forEach(input => {
        let label = this.__createPort(true, input.name);
        this.__inputPorts.add(label);
      });
    },

    setOutputs: function(ouputs) {
      ouputs.forEach(ouput => {
        let label = this.__createPort(false, ouput.name);
        this.__outputPorts.add(label);
      });
    },

    __createPort: function(isInput, name) {
      let label = new qx.ui.basic.Label(name);
      label.portId = qxapp.utils.Utils.uuidv4();
      label.isInput = isInput;
      label.setDraggable(true);
      label.setDroppable(true);
      label.addListener("dragstart", function(e) {
        console.log("Drag");
      }, this);
      return label;
    },

    addInputLinkID: function(linkID) {
      this.getInputLinkIDs().push(linkID);
    },

    addOutputLinkID: function(linkID) {
      this.getOutputLinkIDs().push(linkID);
    }
  }
});
