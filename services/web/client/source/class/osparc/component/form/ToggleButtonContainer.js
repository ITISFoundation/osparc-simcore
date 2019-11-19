/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Container for StudyBrowserListItems or any other ToggleButtons, with some convenient methods.
 */
qx.Class.define("osparc.component.form.ToggleButtonContainer", {
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

    /**
     * Resets the selection so no toggle button is checked.
     */
    resetSelection: function() {
      this.getChildren().map(button => button.setValue(false));
    },

    /**
     * Returns an array that contains all buttons that are checked.
     */
    getSelection: function() {
      return this.getChildren().filter(button => button.getValue());
    },

    /**
     * Sets the given button's value to true (checks it) and unchecks all other buttons. If the given button is not present,
     * every button in the container will get a false value (unchecked).
     * @param {qx.ui.form.ToggleButton} child Button that will be checked
     */
    selectOne: function(child) {
      this.getChildren().map(button => button.setValue(button === child));
    }
  }
});
