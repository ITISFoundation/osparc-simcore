/* ************************************************************************
   Copyright: 2018 ITIS Foundation
   License:   MIT
   Authors:   Odei Maiz <maiz@itis.swiss>
   Utf8Check: äöü
************************************************************************ */

/**
 *  Creates the widget that shows the outputs of the node in a key: value way.
 * If the value is an object, it will show the internal key-value pairs
 * [PortLabel]: [PortValue]
 *
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputLabel", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, port, portKey) {
    this.base();

    this.setNodeModel(nodeModel);

    this._setLayout(new qx.ui.layout.HBox(5));

    let portLabel = this._createChildControlImpl("portLabel");
    portLabel.set({
      value: "<b>" + port.label + "</b>: ",
      toolTip: new qx.ui.tooltip.ToolTip(port.description)
    });

    let portOutput = this._createChildControlImpl("portOutput");
    let outputValue = "Unknown value";
    if (Object.prototype.hasOwnProperty.call(port, "value")) {
      if (typeof port.value === "object") {
        outputValue = this.__pretifyObject(port.value);
      } else {
        outputValue = JSON.stringify(port.value);
      }
    }
    portOutput.set({
      value: outputValue
    });

    this.__createDragMechanism(this, portKey);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      nullable: false
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "portLabel": {
          const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
          control = new qx.ui.basic.Label().set({
            font: title14Font,
            textAlign: "right",
            allowGrowX: true,
            padding: 15,
            rich: true
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "portOutput": {
          const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
          control = new qx.ui.basic.Label().set({
            font: title14Font,
            textAlign: "right",
            allowGrowX: true,
            padding: 15,
            rich: true
          });
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

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
