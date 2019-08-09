/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * SelectBox with its padding and margins adapted to be show inside a qx.ui.toolbar.ToolBar.
 */
qx.Class.define("osparc.ui.toolbar.Label", {
  extend: qx.ui.basic.Label,

  construct: function(value) {
    this.base(arguments, value);
  },

  properties: {
    appearance: {
      refine: true,
      init: "toolbar-label"
    }
  },

  members : {
    // overridden
    _applyVisibility : function(value, old) {
      this.base(arguments, value, old);
      // trigger a appearance recalculation of the parent
      var parent = this.getLayoutParent();
      if (parent && parent instanceof qx.ui.toolbar.PartContainer) {
        qx.ui.core.queue.Appearance.add(parent);
      }
    }
  }
});
