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
  construct: function(message) {
    this.base(arguments, this.tr("Confirmation"));

    if (message) {
      this.setMessage(message);
    }

    const confirmButton = this.getChildControl("confirm-button");
    this.bind("confirmText", confirmButton, "label");

    this.addCancelButton();
  },

  properties: {
    confirmText: {
      check: "String",
      init: "Yes",
      event: "changeConfirmText"
    },

    confirmAction: {
      check: [null, "create", "warning", "delete"],
      init: null,
      nullable: true,
      event: "changeConfirmAction",
    },

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
          control = new qx.ui.form.Button().set({
            appearance: "form-button",
            center: true,
            minWidth: 100,
          });
          control.addListener("execute", () => {
            this.setConfirmed(true);
            this.close(1);
          }, this);
          this.bind("confirmAction", control, "appearance", {
            converter: value => {
              switch (value) {
                case "create":
                  return "strong-button";
                case "warning":
                  return "warning-button";
                case "delete":
                  return "danger-button";
                default:
                  return "strong-button";
              }
            }
          });
          const command = new qx.ui.command.Command("Enter");
          control.setCommand(command);
          const btnsLayout = this.getChildControl("buttons-layout");
          btnsLayout.addAt(control, 1);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    getConfirmButton: function() {
      return this.getChildControl("confirm-button");
    },

    getCancelButton: function() {
      return this.getChildControl("cancel-button");
    },
  }
});
