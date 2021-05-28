/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.basic.Chip", {
  extend: qx.ui.basic.Atom,

  construct: function(label, icon) {
    this.base(arguments, label, icon);
  },

  properties: {
    appearance: {
      init: "chip",
      refine: true
    }
  }
});
