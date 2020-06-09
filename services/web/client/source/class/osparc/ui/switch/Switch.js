/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Switch button
 */

qx.Class.define("osparc.ui.switch.Switch", {
  extend: qx.ui.basic.Image,

  construct: function() {
    this.base(arguments);

    this.set({
      cursor: "pointer",
      backgroundColor: "transparent",
      source: "@FontAwesome5Solid/toggle-on/22"
    });

    this.addListener("tap", () => {
      this.toggleChecked();
    });

    this.initChecked();
  },

  properties: {
    checked: {
      check: "Boolean",
      init: false,
      event: "changeChecked",
      apply: "_applyChecked"
    }
  },

  members: {
    __slider: null,

    _applyChecked: function(newVal) {
      if (newVal) {
        this.getContentElement().addClass("rotated");
      } else {
        this.getContentElement().removeClass("rotated");
      }
    }
  }
});
