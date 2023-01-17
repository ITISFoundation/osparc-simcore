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

    const layout = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    if (text) {
      this.setText(text);
    }

    this.bind("read", this, "backgroundColor", {
      converter: read => read ? "red" : "blue"
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
    MAX_WIDTH: 300
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text":
          control = new qx.ui.basic.Label();
          this.bind("text", control, "value");
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyText: function() {
      this.getChildControl("text");
    }
  }
});
