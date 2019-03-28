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
 * Widget/VirtualTree used for showing SimulatorTree from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorBox", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.Canvas());
    const splitpane = this.__splitpane = new qx.ui.splitpane.Pane("vertical");
    splitpane.getChildControl("splitter").getChildControl("knob")
      .hide();
    splitpane.setOffset(0);

    this._add(splitpane, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    this.__simulatorTree = this.__addSimulatorTree();
    this.__simulatorProps = this.__addSimulatorProps();

    this.__simulatorTree.addListener("selectionChanged", e => {
      const selectedNode = e.getData();
      this.__simulatorProps.setNode(selectedNode);
    }, this);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __splitpane: null,
    __simulatorTree: null,
    __simulatorProps: null,

    __addSimulatorTree: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(0));

      const label = new qx.ui.basic.Label(this.tr("Explorer")).set({
        allowGrowX: true,
        paddingLeft: 10,
        appearance: "toolbar-textfield"
      });
      const simulatorTree = new qxapp.component.widget.simulator.SimulatorTree(this.getNode());

      vBox.add(label);
      vBox.add(simulatorTree, {
        flex: 1
      });

      this.__splitpane.add(vBox);

      return simulatorTree;
    },

    __addSimulatorProps: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(0));

      const label = new qx.ui.basic.Label(this.tr("Properties")).set({
        allowGrowX: true,
        paddingLeft: 10,
        appearance: "toolbar-textfield"
      });
      const simulatorProps = new qxapp.component.widget.simulator.SimulatorProps(this.getNode(), null);

      vBox.add(label);
      vBox.add(simulatorProps, {
        flex: 1
      });

      this.__splitpane.add(vBox);

      return simulatorProps;
    }
  }
});
