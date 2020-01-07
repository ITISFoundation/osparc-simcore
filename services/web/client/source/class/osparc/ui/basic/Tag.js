/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * GitHub-like tag.
 * It has a message and a background color.
 */
qx.Class.define("osparc.ui.basic.Tag", {
  extend: qx.ui.basic.Label,
  construct: function(value, color) {
    this.base(arguments, value);
    if (color) {
      this.setColor(color);
    }
  },
  properties: {
    color: {
      check: "Color",
      nullable: false,
      apply: "_applyColor"
    },
    appearance: {
      init: "tag",
      refine: true
    }
  },
  members: {
    _applyColor: function(color) {
      this.setBackgroundColor(color);
      // set the right color for the font
    }
  }
})