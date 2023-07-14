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
      layout: new qx.ui.layout.VBox(15),
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
      apply: "_applyMessage"
    }
  },

  members: {
    __messageLabel: null,
    __extraWidgetsLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this.add(control);
          break;
        case "cancel-button": {
          const btnsLayout = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            font: "text-14"
          });
          btnsLayout.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.__messageLabel = new qx.ui.basic.Label().set({
        font: "text-14",
        selectable: true,
        rich: true
      });
      this.add(this.__messageLabel, {
        flex: 1
      });

      this.__extraWidgetsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
        paddingTop: 15
      });
      this.__extraWidgetsLayout.exclude();
      this.add(this.__extraWidgetsLayout, {
        flex: 1
      });

      this.getChildControl("buttons-layout");
    },

    _applyMessage: function(message) {
      this.__messageLabel.setValue(message);
    },

    addWidget: function(widget) {
      this.__extraWidgetsLayout.show();
      this.__extraWidgetsLayout.add(widget);
    },

    /**
     * Adds a button to the dialog.
     * @param {qx.ui.form.Button} button Button that will be added to the bottom bar of the dialog.
     */
    addButton: function(button) {
      const btnToolbar = this.getChildControl("buttons-layout");
      button.set({
        font: "text-14"
      });
      btnToolbar.add(button);
    },

    /**
     * Adds a default cancel button to the dialog.
     */
    addCancelButton: function() {
      const cancelButton = this.getChildControl("cancel-button");
      cancelButton.addListener("execute", () => this.close(), this);
      return cancelButton;
    }
  }
});
