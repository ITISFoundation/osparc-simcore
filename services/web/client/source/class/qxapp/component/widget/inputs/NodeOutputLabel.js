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
    this.__portId = portKey;

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnFlex(0, 1);
    grid.setColumnFlex(1, 1);
    grid.setColumnWidth(2, 23);
    this._setLayout(grid);
    this.setPadding([0, 5]);


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

    this.__subscribeToMessages();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __portId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "portLabel": {
          control = new qxapp.ui.basic.Label(14).set({
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
          control = new qxapp.ui.basic.Label(14).set({
            margin: [10, 0],
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
            alignX: "right",
            toolTip: new qx.ui.tooltip.ToolTip("Drag and drop over desired input...")
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
        draggable: true
      });
      uiPort.nodeId = this.getNode().getNodeId();
      uiPort.portId = portKey;

      uiPort.addListener("dragstart", e => {
        // Register supported actions
        e.addAction("copy");
        // Register supported types
        e.addType("osparc-port-link");
      }, this);
    },

    getOutputWidget: function() {
      return this;
    },

    __subscribeToMessages: function() {
      const msgCb = decoratorName => msg => {
        const compareFn = msg.getData();
        if (compareFn(this.getNode().getNodeId(), this.__portId)) {
          if (decoratorName) {
            this.setDecorator(decoratorName);
          } else {
            this.resetDecorator();
          }
        }
      };
      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("inputFocus", msgCb("outputPortHighlighted"));
        qx.event.message.Bus.getInstance().subscribe("inputFocusout", msgCb());
      });
      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("inputFocus", msgCb("outputPortHighlighted"));
        qx.event.message.Bus.getInstance().unsubscribe("inputFocusout", msgCb());
      });
    }
  }
});
