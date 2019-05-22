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

  construct: function(message, level) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(10));

    this.set({
      maxWidth: 250
    });

    const badge = this.getChildControl("badge");
    badge.setBackgroundColor(this.self().LOG_LEVEL_COLOR_MAP[level]);

    if (message) {
      this.setMessage(message);
    }

    this.getChildControl("closebutton");
  },

  properties: {
    appearance: {
      init: "flash",
      refine: true
    },
    message: {
      check: "String",
      nullable: true,
      apply: "_applyMessage"
    }
  },

  statics: {
    LOG_LEVEL_COLOR_MAP: {
      "INFO": "blue",
      "DEBUG": "yellow",
      "WARING": "orange",
      "ERROR": "red"
    }
  },

  events: {
    "closeMessage": "qx.event.type.Event"
  },

  members: {
    __closeCb: null,
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "message":
          control = new qx.ui.basic.Label().set({
            rich: true
          });
          this._add(control);
          break;
        case "closebutton":
          control = new qxapp.component.form.IconButton("@MaterialIcons/close/16", () => this.fireEvent("closeMessage"));
          this._add(control);
          break;
        case "badge":
          control = new qx.ui.core.Widget().set({
            height: 10,
            width: 10,
            allowStretchX: false,
            allowStretchY: false,
            alignY: "middle"
          });
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
