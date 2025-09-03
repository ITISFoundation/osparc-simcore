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
      layout: new qx.ui.layout.VBox(10),
      showMinimize: false,
      showMaximize: false,
      contentPadding: 15,
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
      init: "",
      event: "changeMessage",
    }
  },

  members: {
    __messageLabel: null,
    __extraWidgetsLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "message-label":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            selectable: true,
            rich: true
          });
          this.bind("message", control, "value");
          this.addAt(control, 0);
          break;
        case "extra-widgets-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            paddingTop: 10
          });
          this.addAt(control, 1, {
            flex: 1
          });
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this.addAt(control, 2);
          break;
        case "cancel-button": {
          const btnsLayout = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text"
          });
          btnsLayout.addAt(control, 0);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("message-label");
      this.getChildControl("buttons-layout");
    },

    addWidget: function(widget) {
      this.getChildControl("extra-widgets-layout").add(widget);
    },

    getExtraWidgetsLayout: function() {
      return this.getChildControl("extra-widgets-layout");
    },

    /**
     * Adds a button to the dialog.
     * @param {qx.ui.form.Button} button Button that will be added to the bottom bar of the dialog.
     */
    addButton: function(button) {
      const btnToolbar = this.getChildControl("buttons-layout");
      button.set({
        appearance: "form-button"
      });
      btnToolbar.addAt(button, 1);
    },

    /**
     * Adds a default cancel button to the dialog.
     */
    addCancelButton: function() {
      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.set({
        center: true,
        minWidth: 100
      });
      cancelButton.addListener("execute", () => this.close(), this);
      return cancelButton;
    }
  }
});
