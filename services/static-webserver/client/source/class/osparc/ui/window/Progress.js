/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2025 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Generic progress window.
 */
qx.Class.define("osparc.ui.window.Progress", {
  extend: osparc.ui.window.Dialog,

  construct: function(title, icon, message) {
    this.base(arguments, title, icon, message);

    const progressBar = this.getChildControl("progress-bar");
    this.bind("progress", progressBar, "value");
  },

  properties: {
    progress: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeProgress"
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "progress-bar":
          control = new qx.ui.indicator.ProgressBar().set({
            maximum: 100,
            maxHeight: 12,
            alignX: "center",
            alignY: "middle",
            allowGrowY: false,
            allowGrowX: true,
            margin: 0,
          });
          control.getChildControl("progress").set({
            backgroundColor: "strong-main"
          });
          control.getContentElement().setStyles({
            "border-radius": "4px"
          });
          this.addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
