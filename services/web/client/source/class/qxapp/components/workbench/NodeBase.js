const nodeWidth = 240;
const portHeight = 16;

qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function(uuid) {
    this.base();

    this.set({
      appearance: "window-small-cap",
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

    let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
    this.add(inputsOutputsLayout, {
      flex: 1
    });

    let inputsBox = new qx.ui.layout.VBox(5);
    this.__inputPortsUI = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this.__inputPortsUI, {
      width: "50%"
    });

    let outputsBox = new qx.ui.layout.VBox(5);
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
      left: nodeWidth/2 - 20
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
    },

    viewerButton: {
      init: null,
      check: "qx.ui.form.Button"
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

    __getCurrentBounds: function() {
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
        this.__addSettings(props);
        this.__addViewerButton(metaData);
        this.__addInputPorts(metaData.inputs);
        this.__addOutputPorts(metaData.outputs);
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    __addSettings: function(settings) {
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

    __addViewerButton: function(metadata) {
      if (metadata.viewer) {
        let button = new qx.ui.form.Button("Open Viewer");
        button.setEnabled(metadata.viewer.port !== null);
        this.setViewerButton(button);
      }
    },

    __addInputPort: function(inputData) {
      let label = this.__createPort(true, inputData);
      this.getInputPorts().push(label);
      this.__inputPortsUI.add(label.ui);
    },

    __addOutputPort: function(outputData) {
      let label = this.__createPort(false, outputData);
      this.getOutputPorts().push(label);
      this.__outputPortsUI.add(label.ui);
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

    getPortByIndex: function(isInput, portIdx) {
      const nInPorts = this.getInputPorts().length;
      const nOutPorts = this.getOutputPorts().length;
      if (isInput && portIdx < nInPorts) {
        return this.getInputPorts()[portIdx];
      } else if (!isInput && portIdx < nOutPorts) {
        return this.getOutputPorts()[portIdx];
      }
      return null;
    },

    __addInputPorts: function(inputs) {
      for (let inputData of inputs) {
        this.__addInputPort(inputData);
      }
    },

    __addOutputPorts: function(outputs) {
      for (let outputData of outputs) {
        this.__addOutputPort(outputData);
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
          icon = "@FontAwesome5Solid/file/" + (portHeight-2).toString();
          break;
        case "folder-url":
          icon = "@FontAwesome5Solid/folder/" + (portHeight-2).toString();
          break;
        default:
          icon = "@FontAwesome5Solid/edit/" + (portHeight-2).toString();
          break;
      }
      const alignX = (isInput) ? "left" : "right";
      label.ui = new qx.ui.basic.Atom(portData.key, icon).set({
        height: portHeight,
        draggable: true,
        droppable: true,
        iconPosition: alignX,
        alignX: alignX,
        allowGrowX: false
      });
      label.ui.portId = portData.key;

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

    getLinkPoint: function(port) {
      const nodeBounds = this.__getCurrentBounds();
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      const captionHeight = this.__childControls.captionbar.getBounds().height;
      const inputOutputs = this.getChildren()[0];
      const inputPorts = inputOutputs.getChildren()[0].getChildren();
      const outputPorts = inputOutputs.getChildren()[1].getChildren();
      const ports = inputPorts.concat(outputPorts);
      let portBounds;
      for (let i=0; i<ports.length; i++) {
        if (port.portId === ports[i].portId) {
          portBounds = ports[i].getBounds();
          break;
        }
      }
      let y = nodeBounds.top + captionHeight + 10 + portBounds.top + portBounds.height/2;
      return [x, y];
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
