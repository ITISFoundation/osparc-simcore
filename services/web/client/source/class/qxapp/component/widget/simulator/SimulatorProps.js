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
 *  Widget used for showing SimulatorProps, properties of the selected item
 * in the SimulatorTree
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorProps", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      node: node
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      apply: "_applyNode",
      nullable: false
    }
  },

  members: {
    _applyNode: function() {
      this._removeAll();

      const node = this.getNode();
      if (node && node.getPropsWidget()) {
        const propsWidget = node.getPropsWidget();
        this._add(propsWidget);
      }
    }
  }
});
