/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * A FlashMessage provides brief messages about the app processes. It is used and handled by qxapp.component.message.FlashMessenger.
 */
qx.Class.define("qxapp.ui.message.FlashMessage", {
  extend: qx.ui.core.Widget,

  construct: function(message, level, icon, position) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());
    if (message) {
      this.setMessage(message);
    }
    this.getChildControl("closebutton");
  },

  properties: {
    message: {
      check: "String",
      nullable: true,
      apply: "_applyMessage"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "message":
          control = new qx.ui.basic.Label();
          this._add(control);
          break;
        case "closebutton":
          control = new qxapp.component.form.IconButton("@MaterialIcons/close/16", () => this.exclude());
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyMessage: function(value) {
      const label = this.getChildControl("message");
      if (label) {
        label.setValue(value);
      }
    }
  }
});
