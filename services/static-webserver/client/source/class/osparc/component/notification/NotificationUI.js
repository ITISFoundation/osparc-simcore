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

qx.Class.define("osparc.component.notification.NotificationUI", {
  extend: qx.ui.core.Widget,

  construct: function(text) {
    this.base(arguments);

    this.set({
      maxWidth: this.self().MAX_WIDTH,
      padding: this.self().PADDING
    });

    const layout = new qx.ui.layout.HBox().set({
      alignY: "middle"
    });
    this._setLayout(layout);

    if (text) {
      this.setText(text);
    }

    this.bind("read", this, "backgroundColor", {
      converter: read => read ? "background-main-3" : "background-main-4"
    });
  },

  properties: {
    text: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeText",
      apply: "__applyText"
    },

    read: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeRead"
    }
  },

  statics: {
    MAX_WIDTH: 300,
    PADDING: 10
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text":
          control = new qx.ui.basic.Label().set({
            maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
            font: "text-14",
            rich: true,
            wrap: true
          });
          this.bind("text", control, "value");
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyText: function() {
      this.getChildControl("text");
    }
  }
});
