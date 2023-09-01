/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.navigation.BreadcrumbNavigation", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(0).set({
      alignY: "middle"
    }));
  },

  members: {
    /**
      * @abstract
      */
    populateButtons: function(nodesIds = []) {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    _createBtns: function(nodeId) {
      throw new Error("Abstract method called!");
    }
  }
});
