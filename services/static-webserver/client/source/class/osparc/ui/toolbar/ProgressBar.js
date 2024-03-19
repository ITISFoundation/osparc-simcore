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
 * ProgressBar with its padding and margins adapted to be show inside a qx.ui.toolbar.ToolBar.
 */
qx.Class.define("osparc.ui.toolbar.ProgressBar", {
  extend: qx.ui.indicator.ProgressBar,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    appearance: {
      refine: true,
      init: "toolbar-progressbar"
    }
  },

  members : {
    // overridden
    _applyVisibility : function(value, old) {
      this.base(arguments, value, old);
      // trigger a appearance recalculation of the parent
      const parent = this.getLayoutParent();
      if (parent && parent instanceof qx.ui.toolbar.PartContainer) {
        qx.ui.core.queue.Appearance.add(parent);
      }
    }
  }
});
