/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const simulator = new qxapp.component.widget.simulator.Simulator(node);
 *   this.getRoot().add(simulator);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.simulator.Simulator", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.Canvas());
    const splitpane = this.__splitpane = new qx.ui.splitpane.Pane("horizontal");
    splitpane.getChildControl("splitter").getChildControl("knob")
      .hide();
    splitpane.setOffset(0);

    this._add(splitpane, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    const SimulatorBox = this.__SimulatorBox = new qxapp.component.widget.simulator.SimulatorBox(node);
    const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    vBox.add(SimulatorBox, {
      flex: 1
    });
    vBox.setWidth(250);
    vBox.setMinWidth(150);
    splitpane.add(vBox, 0);

    this.__checkModelerIsConnected();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __splitpane: null,
    __SimulatorBox: null,
    __modeler: null,

    __checkModelerIsConnected: function() {
      const inputNodes = this.getNode().getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        if (inputNodes[i].isInKey("remote-renderer")) {
          const modeler = this.__modeler = new qxapp.component.widget.RemoteRenderer(inputNodes[i], null);
          this.__splitpane.add(modeler, 1);
          break;
        }
      }
    }
  }
});
