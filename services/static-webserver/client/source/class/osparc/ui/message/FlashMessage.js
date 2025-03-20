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
    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 18,
      maxWidth: 400,
      allowStretchX: false,
      alignX: "center",
      backgroundColor: this.self().LOG_LEVEL_COLOR_MAP[level].backgroundColor,
      decorator: `flash-${this.self().LOG_LEVEL_COLOR_MAP[level].color}`
    });

    const badge = this.getChildControl("badge");
    badge.set({
      source: this.self().LOG_LEVEL_COLOR_MAP[level].icon+"16",
      textColor: this.self().LOG_LEVEL_COLOR_MAP[level].color
    });

    this.setMessage(message);

    if ([null, undefined].includes(duration)) {
      const wordCount = message.split(" ").length;
      duration = Math.max(5500, wordCount*500); // An average reader takes 300ms to read a word
    }
    this.setDuration(duration);

    this.getChildControl("closebutton");
  },

  properties: {
    appearance: {
      init: "flash",
      refine: true
    },

    message: {
      check: "String",
      nullable: false,
      apply: "__applyMessage",
    },

    duration: {
      check: "Number",
      init: null,
      nullable: true,
    }
  },

  statics: {
    LOG_LEVEL_COLOR_MAP: {
      "INFO": {
        color: "info",
        icon: "@FontAwesome5Solid/check/",
        backgroundColor: "flash_message_bg"
      },
      "DEBUG": {
        color: "warning",
        icon: "@FontAwesome5Solid/info/",
        backgroundColor: "flash_message_bg"
      },
      "WARNING": {
        color: "warning",
        icon: "@FontAwesome5Solid/exclamation-triangle/",
        backgroundColor: "flash_message_bg"
      },
      "ERROR": {
        color: "error",
        icon: "@FontAwesome5Solid/exclamation/",
        backgroundColor: "flash_message_bg"
      }
    }
  },

  events: {
    "closeMessage": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "message-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(15));
          this._add(control);
          break;
        case "badge":
          control = new qx.ui.basic.Image().set({
            alignY: "middle"
          });
          this.getChildControl("message-layout").addAt(control, 0);
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            selectable: true,
            rich: true
          });
          this.getChildControl("message-layout").addAt(control, 1, {
            flex: 1
          });
          break;
        case "closebutton":
          control = new osparc.ui.basic.IconButton("@MaterialIcons/close/16", () => this.fireEvent("closeMessage")).set({
            alignY: "middle"
          });
          this.getChildControl("message-layout").addAt(control, 2);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyMessage: function(value) {
      this.getChildControl("message").setValue(value);
    },

    addWidget: function(widget) {
      this._add(widget);
    },
  }
});
