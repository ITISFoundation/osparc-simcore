const nodeWidth = 180;
const portHeight = 16;

qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function(nodeModel) {
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

    this.setNodeModel(nodeModel);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  events: {
    "LinkDragStart": "qx.event.type.Data",
    "LinkDragOver": "qx.event.type.Data",
    "LinkDrop": "qx.event.type.Data",
    "LinkDragEnd": "qx.event.type.Data",
    "NodeMoving": "qx.event.type.Event"
  },

  members: {
    __inputPorts: null,
    __outputPorts: null,
    __inputPortsUI: null,
    __outputPortsUI: null,
    __progressLabel: null,
    __progressBar: null,
    __innerNodes: null,
    __connectedTo: null,

    getNodeId: function() {
      return this.getNodeModel().getNodeId();
    },

    getMetaData: function() {
      return this.getNodeModel().getMetaData();
    },

    getInnerNodes: function() {
      return this.getNodeModel().getInnerNodes();
    },

    addLink: function(link) {
      this.getNodeModel().addLink(link);
    },

    removeLink: function(link) {
      this.getNodeModel().removeLink(link);
    },

    createNodeLayout: function() {
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
    },

    populateNodeLayout: function() {
      const metaData = this.getNodeModel().getMetaData();
      this.setCaption(metaData.name + " " + metaData.version);
      this.__outputPorts = {};
      this.__inputPorts = {};
      this.__createPorts("Input", metaData.inputs);
      this.__createPorts("Output", metaData.outputs);
    },

    getInputPorts: function() {
      return this.__inputPorts;
    },

    getInputPort: function(portId) {
      // return this.__inputPorts[portId];
      return this.__inputPorts["Input"];
    },

    getOutputPorts: function() {
      return this.__outputPorts;
    },

    getOutputPort: function(portId) {
      // return this.__outputPorts[portId];
      return this.__outputPorts["Output"];
    },

    __createPorts: function(portId, ports) {
      const nPorts = Object.keys(ports).length;
      if (nPorts < 1) {
        return;
      }
      switch (portId) {
        case "Input": {
          let label = this.__createPort(true, portId, ports);
          this.getInputPorts()[portId] = label;
          this.__inputPortsUI.add(label.ui);
        }
          break;
        case "Output": {
          let label = this.__createPort(false, portId, ports);
          this.getOutputPorts()[portId] = label;
          this.__outputPortsUI.add(label.ui);
        }
          break;
      }
    },

    __createPort: function(isInput, portId, portsData) {
      let label = {};
      label.portId = portId;
      label.isInput = isInput;
      const labelText = (isInput) ? "Input(s)" : "Output(s)";
      const alignX = (isInput) ? "left" : "right";
      label.ui = new qx.ui.basic.Atom(labelText).set({
        height: portHeight,
        draggable: true,
        droppable: true,
        alignX: alignX,
        allowGrowX: false
      });
      label.ui.portId = portId;

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
            portId: portId,
            isInput: isInput
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
      return label;
    },

    getLinkPoint: function(port) {
      const nodeBounds = this.getCurrentBounds();
      let x = nodeBounds.left;
      if (port.isInput === false) {
        x += nodeBounds.width;
      }
      const captionHeight = this.__childControls.captionbar.getBounds().height;
      const inputOutputs = this.getChildren()[0];
      let ports = null;
      if (port.isInput) {
        ports = inputOutputs.getChildren()[0].getChildren();
      } else {
        ports = inputOutputs.getChildren()[1].getChildren();
      }
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

    setProgress: function(progress) {
      this.__progressLabel.setValue(progress + "%");
      this.__progressBar.setValue(progress);
    },

    getProgress: function() {
      return this.__progressBar.getValue();
    },

    // override qx.ui.window.Window "move" event listener
    _onMovePointerMove: function(e) {
      this.base(arguments, e);
      if (e.getPropagationStopped() === true) {
        this.fireEvent("NodeMoving");
      }
    }
  }
});
