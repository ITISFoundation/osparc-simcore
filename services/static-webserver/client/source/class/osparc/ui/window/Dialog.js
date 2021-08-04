/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Generic window to prompt the user with useful information. Provides functions to add buttons.
 * extends
 */
qx.Class.define("osparc.ui.window.Dialog", {
  extend: osparc.ui.window.Window,
  /**
   * Constructor takes the same parameters as the Qooxdoo window widget, only adding a message that will
   * be displayed to the user.
   * @extends osparc.ui.window.Window
   * @param {String} message Message that will be displayed to the user.
   */
  construct: function(caption, icon, message) {
    this.base(arguments, caption, icon);
    this.set({
      autoDestroy: true,
      layout: new qx.ui.layout.VBox(),
      showMinimize: false,
      showMaximize: false,
      contentPadding: 0,
      maxWidth: 350,
      resizable: false,
      modal: true
    });
    this.__buildLayout();
    if (message) {
      this.setMessage(message);
    }
    this.center();
  },

  properties: {
    message: {
      check: "String",
      apply: "_applyMessage"
    }
  },

  members: {
    __messageLabel: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "buttons-toolbar":
          control = new qx.ui.toolbar.ToolBar();
          control.addSpacer();
          this.add(control);
          break;
        case "cancel-button": {
          const btnToolbar = this.getChildControl("buttons-toolbar");
          control = new qx.ui.toolbar.Button(this.tr("Cancel"));
          btnToolbar.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.__messageLabel = new qx.ui.basic.Label().set({
        rich: true,
        padding: 10
      });
      this.add(this.__messageLabel, {
        flex: 1
      });
      this.getChildControl("buttons-toolbar");
    },

    _applyMessage: function(message) {
      this.__messageLabel.setValue(message);
    },

    /**
     * Adds a button to the dialog.
     * @param {qx.ui.toolbar.Button} button Button that will be added to the bottom bar of the dialog.
     */
    addButton: function(button) {
      const btnToolbar = this.getChildControl("buttons-toolbar");
      btnToolbar.add(button);
    },

    /**
     * Adds a default cancel button to the dialog.
     */
    addCancelButton: function() {
      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.addListener("execute", () => this.close(), this);
    }
  }
});
