/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Container for StudyBrowserListItems or any other ToggleButtons, with some convenient methods. Applies a default Flow layout.
 */
qx.Class.define("qxapp.component.form.ToggleButtonContainer", {
  extend: qx.ui.container.Composite,

  construct: function(layout) {
    this.base(arguments, layout);
  },

  events: {
    changeSelection: "qx.event.type.Data"
  },

  members: {
    // overriden
    add: function(child, options) {
      if (child instanceof qx.ui.form.ToggleButton) {
        this.base(arguments, child, options);
        child.addListener("changeValue", e => {
          this.fireDataEvent("changeSelection", this.getSelection());
        }, this);
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    resetSelection: function() {
      this.getChildren().map(button => button.setValue(false));
    },

    getSelection: function() {
      return this.getChildren().filter(button => button.getValue());
    },

    selectOne: function(child) {
      this.getChildren().map(button => button.setValue(button === child));
    }
  }
});
