/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.node.UpdateResourceLimitsView", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(5));

    if (node) {
      this.setNode(node);
    }
  },

  events: {
    "limitsChanged": "qx.event.type.Event"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    }
  },

  members: {
    __applyNode: function(node) {
      if (node.isComputational() || node.isDynamic()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Update limits Options")).set({
        font: "text-14"
      }));
    }
  }
});
