/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * A FlashMessage provides brief messages about the app processes. It is used and handled by osparc.FlashMessenger.
 */
qx.Class.define("osparc.ui.message.FlashMessage", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor for the FlashMessage.
   *
   * @param {String} message Message that the user will read.
   * @param {String="INFO","DEBUG","WARNING","ERROR"} level Logging level of the message. Each level has different, distinct color.
   * @param {Number} duration
   */
  construct: function(message, level, duration) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(15));

    this.set({
      padding: 18,
      maxWidth: 400,
      allowStretchX: false,
      alignX: "center"
    });

    const badge = this.getChildControl("badge");
    badge.set({
      source: this.self().LOG_LEVEL_COLOR_MAP[level].icon+"16",
      textColor: this.self().LOG_LEVEL_COLOR_MAP[level].color
    });

    if (message) {
      this.setMessage(message);
    }

    if (duration) {
      this.setDuration(duration);
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
      apply: "__applyMessage"
    },

    duration: {
      check: "Number",
      nullable: true
    }
  },

  statics: {
    LOG_LEVEL_COLOR_MAP: {
      "INFO": {
        color: "ready-green",
        icon: "@FontAwesome5Solid/check/"
      },
      "DEBUG": {
        color: "warning-yellow",
        icon: "@FontAwesome5Solid/info/"
      },
      "WARNING": {
        color: "busy-orange",
        icon: "@FontAwesome5Solid/exclamation-triangle/"
      },
      "ERROR": {
        color: "failed-red",
        icon: "@FontAwesome5Solid/exclamation/"
      }
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
        case "badge":
          control = new qx.ui.basic.Image().set({
            alignY: "middle"
          });
          this._add(control);
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            selectable: true,
            rich: true
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "closebutton":
          control = new osparc.ui.basic.IconButton("@MaterialIcons/close/16", () => this.fireEvent("closeMessage")).set({
            alignY: "middle"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyMessage: function(value) {
      const label = this.getChildControl("message");
      if (label) {
        label.setValue(value);
      }
    }
  }
});
