/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.node.ProbeView", {
  extend: qx.ui.core.Widget,

  construct: function(probe) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    if (probe) {
      this.setNode(probe);
    }
  },

  statics: {
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    },
  },

  members: {
    __applyNode: function(node) {
      if (!node.isProbe()) {
        console.error("Only Probe nodes are supported");
      }
      this.__populateLayout(node);
    },

    __populateLayout: function(node) {
      const inputsForm = node.getPropsForm();
      const inputs = new osparc.desktop.PanelView(this.tr("Inputs"), inputsForm);
      inputs._innerContainer.set({
        margin: 8
      });
      this._add(inputs);
    }
  }
});
