qx.Class.define("qxapp.component.widget.NodePorts", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel) {
    this.base();

    let nodeInputLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeInputLayout);

    this.set({
      decorator: "main"
    });

    let atom = new qx.ui.basic.Atom().set({
      label: nodeModel.getLabel(),
      center : true
    });

    this._add(atom);

    this.setNodeModel(nodeModel);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  events: {
    "PortDragStart": "qx.event.type.Data"
  },

  members: {
    __inputPort: null,
    __outputPort: null,

    getNodeId: function() {
      return this.getNodeModel().getNodeId();
    },

    getMetaData: function() {
      return this.getNodeModel().getMetaData();
    },

    populateNodeLayout: function() {
      const metaData = this.getNodeModel().getMetaData();
      this.__inputPort = {};
      this.__outputPort = {};
      // this.__createUIPorts(true, metaData.inputs);
      this.__createUIPorts(false, metaData.outputs);
    },

    getInputPort: function() {
      return this.__inputPort["Input"];
    },

    getOutputPort: function() {
      return this.__outputPort["Output"];
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNodeModel().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      for (const portKey in ports) {
        const port = ports[portKey];
        if (port.type.includes("api")) {
          console.log("Provide widget for ", port.type);
        } else {
          let toolTip = new qx.ui.tooltip.ToolTip(port.description);
          let portLabel = new qx.ui.basic.Label(port.label).set({
            draggable: true,
            toolTip: toolTip,
            textAlign: "right",
            allowGrowX: true,
            paddingRight: 20
          });
          this._add(portLabel);
          this.__createUIPortConnections(portLabel, portKey);
          let label = {
            isInput: isInput,
            ui: portLabel
          };
          label.ui.isInput = isInput;
          if (isInput) {
            this.__inputPort["Input"] = label;
          } else {
            this.__outputPort["Output"] = label;
          }
        }
      }
    },

    __createUIPortConnections: function(uiPort, portId) {
      [
        ["dragstart", "PortDragStart"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeId(),
            portId: portId
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    getLinkPoint: function(port) {
      if (port.isInput === true) {
        console.log("Port should always be output");
        return null;
      }
      let nodeBounds = this.getCurrentBounds();
      if (nodeBounds === null) {
        // not rendered yet
        return null;
      }
      // It is always on the very left of the Desktop
      let x = 0;
      let y = nodeBounds.top + nodeBounds.height/2;
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
    }
  }
});
