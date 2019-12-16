/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.window.Dialog", {
  extend: qx.ui.window.Window,
  construct: function(caption, icon, message) {
    this.base(arguments, caption, icon);
    this.set({
      autoDestroy: true,
      layout: new qx.ui.layout.VBox(),
      appearance: "service-window",
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
    __btnToolbar: null,
    __buildLayout: function() {
      this.__messageLabel = new qx.ui.basic.Label().set({
        rich: true,
        appearance: "dialog-window-content",
        padding: 10
      });
      this.add(this.__messageLabel, {
        flex: 1
      });
      this.__btnToolbar = new qx.ui.toolbar.ToolBar();
      this.__btnToolbar.addSpacer();
      this.add(this.__btnToolbar);
    },
    _applyMessage: function(message) {
      this.__messageLabel.setValue(message);
    },
    addButton: function(button) {
      this.__btnToolbar.add(button);
    },
    addCancelButton: function() {
      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel"));
      cancelButton.addListener("execute", () => this.close(), this);
      this.addButton(cancelButton);
    }
  }
});
