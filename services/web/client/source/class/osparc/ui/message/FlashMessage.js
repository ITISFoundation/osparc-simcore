/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * A FlashMessage provides brief messages about the app processes. It is used and handled by osparc.component.message.FlashMessenger.
 */
qx.Class.define("osparc.ui.message.FlashMessage", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor for the FlashMessage.
   *
   * @param {String} message Message that the user will read.
   * @param {String="INFO","DEBUG","WARNING","ERROR"} level Logging level of the message. Each level has different, distinct color.
   */
  construct: function(message, level) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(10));

    this.set({
      maxWidth: 340,
      allowStretchX: false,
      alignX: "center"
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
      "WARNING": "orange",
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
          this._add(control, {
            flex: 1
          });
          break;
        case "closebutton":
          control = new osparc.component.form.IconButton("@MaterialIcons/close/16", () => this.fireEvent("closeMessage")).set({
            alignY: "middle"
          });
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
