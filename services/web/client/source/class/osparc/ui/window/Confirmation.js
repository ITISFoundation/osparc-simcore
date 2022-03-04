/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Generic confirmation window.
 * Provides "Cancel" and "Yes" buttons as well as boolean Confirmed property.
 */
qx.Class.define("osparc.ui.window.Confirmation", {
  extend: osparc.ui.window.Dialog,

  /**
   * @extends osparc.ui.window.Dialog
   * @param {String} message Message that will be displayed to the user.
   */
  construct: function(message, confirmBtnText = this.tr("Yes")) {
    this.base(arguments, this.tr("Confirmation"), null, message);

    this.addCancelButton();

    this.getChildControl("confirm-button").set({
      label: confirmBtnText
    });
  },

  properties: {
    confirmed: {
      check: "Boolean",
      init: false
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "confirm-button": {
          control = new qx.ui.form.Button();
          control.addListener("execute", () => {
            this.setConfirmed(true);
            this.close(1);
          }, this);
          const command = new qx.ui.command.Command("Enter");
          control.setCommand(command);
          this.addButton(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    getConfirmButton: function() {
      return this.getChildControl("confirm-button");
    }
  }
});
