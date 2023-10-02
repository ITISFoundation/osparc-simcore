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

    this.addCancelButton();

    const confirmButton = this.__confirmButton = new qx.ui.form.Button();
    this.bind("confirmText", confirmButton, "label");
    confirmButton.addListener("execute", () => {
      this.setConfirmed(true);
      this.close(1);
    }, this);
    const command = new qx.ui.command.Command("Enter");
    confirmButton.setCommand(command);
    this.addButton(confirmButton);
  },

  properties: {
    confirmText: {
      check: "String",
      init: "Yes",
      event: "changeConfirmText"
    },

    confirmAction: {
      check: [null, "create", "delete"],
      init: null,
      nullable: true,
      apply: "__applyConfirmAppearance"
    },

    confirmed: {
      check: "Boolean",
      init: false
    }
  },

  members: {
    __confirmButton: null,

    getConfirmButton: function() {
      return this.__confirmButton;
    },

    getCancelButton: function() {
      return this.getChildControl("cancel-button");
    },

    __applyConfirmAppearance: function(confirmationAction) {
      const confBtn = this.__confirmButton;
      switch (confirmationAction) {
        case "create":
          confBtn.setAppearance("strong-button");
          break;
        case "delete":
          confBtn.setAppearance("danger-button");
          break;
        default:
          confBtn.resetAppearance();
          break;
      }
    }
  }
});
