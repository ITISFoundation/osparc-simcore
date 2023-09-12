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

qx.Class.define("osparc.node.ServiceOptionsView", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function(node) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(5));

    if (node) {
      this.setNode(node);
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "_applyNode"
    }
  },

  /**
    * @abstract
    */
  members: {
    _applyNode: function() {
      throw new Error("Abstract method called!");
    }
  }
});
