/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ResourceUpgradeHelper", {
  extend: osparc.ui.window.Dialog,
  /**
   * @extends osparc.ui.window.Dialog
   * @param {String} message Message that will be displayed to the user.
   */
  construct: function(message) {
    this.base(arguments, this.tr("Outdated services"));

    if (message) {
      this.setMessage(message);
    }

    // Secondary action - Left button
    const secondaryButton = this.__secondaryButton = new qx.ui.form.Button();
    secondaryButton.set({
      center: true,
      minWidth: 100
    });
    this.bind("secondaryText", secondaryButton, "label");
    secondaryButton.addListener("execute", () => {
      this.setConfirmed(false);
    }, this);
    this.addButton(secondaryButton);

    // Primary action - Right button
    const primaryButton = this.__confirmButton = new qx.ui.form.Button();
    primaryButton.set({
      center: true,
      minWidth: 100
    });
    this.bind("primaryText", primaryButton, "label");
    primaryButton.addListener("execute", () => {
      this.setConfirmed(true);
    }, this);
    const command = new qx.ui.command.Command("Enter");
    primaryButton.setCommand(command);
    this.addButton(primaryButton);
  },

  properties: {
    primaryText: {
      check: "String",
      init: "Yes",
      event: "changeConfirmText"
    },

    primaryAction: {
      check: [null, "create", "delete"],
      init: null,
      nullable: true,
      apply: "__applyPrimaryAppearance"
    },

    secondaryText: {
      check: "String",
      init: "No",
      event: "changeSecondaryText"
    },

    secondaryAction: {
      check: [null, "primary", "secondary", "text"],
      init: null,
      nullable: true,
      apply: "__applySecondaryAppearance"
    },

    confirmed: {
      check: "Boolean",
      init: null,
      event: "changeConfirmed"
    }
  },

  members: {
    __primaryButton: null,
    __secondaryButton: null,

    getPrimaryButton: function() {
      return this.__primaryButton;
    },

    getSecondaryButton: function() {
      return this.__secondaryButton;
    },

    __applyPrimaryAppearance: function(primaryAction) {
      const primaryBtn = this.__confirmButton;
      switch (primaryAction) {
        case "create":
          primaryBtn.setAppearance("form-button");
          break;
        default:
          primaryBtn.resetAppearance();
          break;
      }
    },

    __applySecondaryAppearance: function(secondaryAction) {
      const secondBtn = this.__secondaryButton;
      switch (secondaryAction) {
        case "primary":
          secondBtn.setAppearance("form-button-outlined");
          break;
        default:
          secondBtn.setAppearance("form-button-text");
          break;
      }
    }
  }
});
