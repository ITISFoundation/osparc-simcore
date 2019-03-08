/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Widget that shows the outputs of the node in a [key : value] way.
 * If the value is an object, it will show the internal key-value pairs
 * [PortLabel]: [PortValue]. It provides Drag mechanism.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeOutputLabel = new qxapp.component.widget.inputs.NodeOutputLabel(node, port, portKey);
 *   widget = nodeOutputLabel.getOutputWidget();
 *   this.getRoot().add(widget);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputLabel", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param port {Object} Port owning the widget
    * @param portKey {String} Port Key
  */
  construct: function(node, port, portKey) {
    this.base();

    this.setNode(node);

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnFlex(0, 1);
    grid.setColumnFlex(1, 1);
    grid.setColumnWidth(2, 23);
    this._setLayout(grid);


    let portLabel = this._createChildControlImpl("portLabel");
    portLabel.set({
      value: "<b>" + port.label + "</b>: ",
      toolTip: new qx.ui.tooltip.ToolTip(port.description)
    });

    let portOutput = this._createChildControlImpl("portOutput");
    let outputValue = "Unknown value";
    let toolTip = "";
    if (port.value) {
      if (typeof port.value === "object") {
        outputValue = qxapp.utils.Utils.pretifyObject(port.value, true);
        toolTip = qxapp.utils.Utils.pretifyObject(port.value, false);
      } else {
        outputValue = JSON.stringify(port.value);
      }
    }
    portOutput.set({
      value: outputValue,
      toolTip: new qx.ui.tooltip.ToolTip(toolTip).set({
        rich: true
      })
    });

    this._createChildControlImpl("dragIcon");

    this.__createDragMechanism(this, portKey);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  events: {
    "dragStart": "qx.event.type.Data",
    "dragEnd": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "portLabel": {
          const text14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["text-14"]);
          control = new qx.ui.basic.Label().set({
            font: text14Font,
            margin: [10, 0],
            rich: true,
            alignX: "right"
          });
          this._add(control, {
            row: 0,
            column: 0
          });
          break;
        }
        case "portOutput": {
          const text14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["text-14"]);
          control = new qx.ui.basic.Label().set({
            font: text14Font,
            margin: [10, 0],
            maxWidth: 250,
            rich: true,
            alignX: "left"
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "dragIcon": {
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/arrows-alt/14",
            alignX: "center"
          });
          this._add(control, {
            row: 0,
            column: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __createDragMechanism: function(uiPort, portKey) {
      uiPort.set({
        draggable: true,
        decorator: "draggableWidget"
      });
      uiPort.nodeId = this.getNode().getNodeId();
      uiPort.portId = portKey;

      uiPort.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");
        // Register supported types
        e.addType("osparc-port-link");
        // Fire data event for someone to catch it
        this.fireDataEvent("dragStart", {
          event: e,
          action: "copy",
          type: "osparc-port-link"
        });
      }, this);

      uiPort.addListener("dragend", e => {
        this.fireDataEvent("dragEnd");
      }, this);
    },

    getOutputWidget: function() {
      return this;
    }
  }
});
