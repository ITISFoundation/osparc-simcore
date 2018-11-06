qx.Class.define("qxapp.component.widget.inputs.NodeOutputLabel", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    let toolTip = new qx.ui.tooltip.ToolTip(port.description);
    let portLabel = this.__portLabel = new qx.ui.basic.Label(port.label).set({
      draggable: true,
      toolTip: toolTip,
      textAlign: "right",
      allowGrowX: true,
      paddingRight: 20
    });

    this.__createUIPortConnections(portLabel, portKey);
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
    __portLabel: null,

    __createUIPortConnections: function(uiPort, portId) {
      [
        ["dragstart", "PortDragStart"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeModel().getNodeId(),
            portId: portId
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    getOutputWidget: function() {
      return this.__portLabel;
    }
  }
});
