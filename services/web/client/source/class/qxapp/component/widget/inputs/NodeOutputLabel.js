qx.Class.define("qxapp.component.widget.inputs.NodeOutputLabel", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    let toolTip = new qx.ui.tooltip.ToolTip(port.description);
    let portLabel = this.__portLabel = new qx.ui.basic.Label(port.label).set({
      toolTip: toolTip,
      textAlign: "right",
      allowGrowX: true,
      paddingRight: 20
    });

    this.__createDragMechanism(portLabel, portKey);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
    __portLabel: null,

    __createDragMechanism: function(uiPort, portKey) {
      uiPort.setDraggable(true);
      uiPort.nodeId = this.getNodeModel().getNodeId();
      uiPort.portId = portKey;

      uiPort.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");
        // Register supported types
        e.addType("osparc-port-link");
      }, this);
    },

    getOutputWidget: function() {
      return this.__portLabel;
    }
  }
});
