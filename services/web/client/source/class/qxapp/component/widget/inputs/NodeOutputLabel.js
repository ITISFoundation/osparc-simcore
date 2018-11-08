qx.Class.define("qxapp.component.widget.inputs.NodeOutputLabel", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    this._setLayout(new qx.ui.layout.HBox(5));

    const toolTip = new qx.ui.tooltip.ToolTip(port.description);
    const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
    let portLabel = new qx.ui.basic.Label("<b>" + port.label + "</b>: ").set({
      toolTip: toolTip,
      font: title14Font,
      textAlign: "right",
      allowGrowX: true,
      padding: 15,
      rich: true
    });

    let outputValue = "Unknown value";
    if (Object.prototype.hasOwnProperty.call(port, "value")) {
      if (typeof port.value === "object") {
        outputValue = this.__pretifyObject(port.value);
      } else {
        outputValue = JSON.stringify(port.value);
      }
    }
    let portValue = new qx.ui.basic.Label().set({
      toolTip: toolTip,
      font: title14Font,
      textAlign: "right",
      allowGrowX: true,
      padding: 15,
      rich: true,
      value: outputValue
    });

    this._add(portLabel, {
      flex: 1
    });
    this._add(portValue);

    this.__createDragMechanism(this, portKey);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
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

    __pretifyObject: function(object) {
      let myText = "";
      const entries = Object.entries(object);
      for (let i=0; i<entries.length; i++) {
        const entry = entries[i];
        myText += String(entry[0]);
        myText += ": ";
        myText += String(entry[1]);
        myText += "<br/>";
      }
      return myText;
    },

    getOutputWidget: function() {
      return this;
    }
  }
});
