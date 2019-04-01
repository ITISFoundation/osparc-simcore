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
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorActions", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.Toolbar());

    const newSettings = this.__newSettings = new qx.ui.toolbar.MenuButton(this.tr("New Settings"));
    this._add(newSettings);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    addNewSettings: function() {
      
    }
  }
});
