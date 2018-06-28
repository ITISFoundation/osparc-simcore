qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function(uuid) {
    this.base();

    const nodeWidth = 240;
    this.set({
      // appearance: "window-small-cap",
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      minWidth: nodeWidth,
      maxWidth: nodeWidth
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
    progressBox.setMinWidth(nodeWidth-20);

    this.__progressBar = new qx.ui.indicator.ProgressBar();
    this.__progressBar.setWidth(nodeWidth-20);
    progressBox.add(this.__progressBar, {
      top: 0,
      left: 0
    });

    this.__progressLabel = new qx.ui.basic.Label("0%");
    progressBox.add(this.__progressLabel, {
      top: 3,
      left: nodeWidth/2 - 10
    });

    this.add(progressBox);


    this.__inputPorts = [];
    this.__outputPorts = [];
    if (uuid === undefined) {
      this.setNodeId(qxapp.utils.Utils.uuidv4());
    } else {
      this.setNodeId(uuid);
    }
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

    propsWidget: {
      check: "qxapp.components.form.renderer.PropForm"
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
    __settingsForm: null,
    __progressBar: null,

    getInputPorts: function() {
      return this.__inputPorts;
    },

    getOutputPorts: function() {
      return this.__outputPorts;
    },

    getProp: function(key) {
      return this.getPropsWidget().getData()[key];
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

    __applyMetadata: function(metaData, old) {
      if (metaData != undefined) {
        this.set({
          serviceName: metaData.name,
          nodeImageId: metaData.key
        });
        let props = metaData.inputs.concat(metaData.settings);
        this.addSettings(props);
        this.addInputs(metaData.inputs);
        this.addOutputs(metaData.outputs);
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    addSettings: function(settings) {
      let form = this.__settingsForm = new qxapp.components.form.Auto(settings);
      this.__settingsForm.addListener("changeData", function(e) {
        let settingsForm = e.getData();
        for (var settingKey in settingsForm) {
          if (this.getMetadata().inputs) {
            for (let i=0; i<this.getMetadata().inputs.length; i++) {
              if (settingKey === this.getMetadata().inputs[i].key) {
                this.getMetadata().inputs[i].value = settingsForm[settingKey];
              }
            }
          }
          if (this.getMetadata().settings) {
            for (let i=0; i<this.getMetadata().settings.length; i++) {
              if (settingKey === this.getMetadata().settings[i].key) {
                this.getMetadata().settings[i].value = settingsForm[settingKey];
              }
            }
          }
        }
      }, this);
      this.setPropsWidget(new qxapp.components.form.renderer.PropForm(form));
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

      let icon = null;
      switch (portData.type) {
        case "file-url":
          icon = "@FontAwesome5Solid/file/16";
          break;
        case "folder-url":
          icon = "@FontAwesome5Solid/folder/16";
          break;
        default:
          icon = "@FontAwesome5Solid/edit/16";
          break;
      }
      const alignX = (isInput) ? "left" : "right";
      label.ui = new qx.ui.basic.Atom(portData.key, icon).set({
        height: 16,
        draggable: true,
        droppable: true,
        iconPosition: alignX,
        alignX: alignX
      });

      var tooltip = new qx.ui.tooltip.ToolTip(portData.key, icon);
      tooltip.setShowTimeout(50);
      label.ui.setToolTip(tooltip);

      [
        ["dragstart", "LinkDragStart"],
        ["dragover", "LinkDragOver"],
        ["drop", "LinkDrop"],
        ["dragend", "LinkDragEnd"]
      ].forEach(eventPair => {
        label.ui.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeId(),
            portId: label.portId
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
      return label;
    },

    setProgress: function(progress) {
      this.__progressLabel.setValue(progress + "%");
      this.__progressBar.setValue(progress);
    },

    getProgress: function() {
      return this.__progressBar.getValue();
    }
  }
});
