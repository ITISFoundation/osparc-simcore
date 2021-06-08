/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.basic.ChipClose", {
  extend: qx.ui.container.Composite,

  construct: function(data, caption) {
    const l = new qx.ui.layout.Atom();
    l.setGap(4);

    this.base(arguments);
    this._setLayout(l);

    this.__init();

    if (typeof data !== "undefined") {
      this.setData(data);
    }
    if (typeof caption !== "undefined") {
      this.setCaption(caption);
    }
  },

  events: {
    deleteClicked: "qx.event.type.Event"
  },

  properties: {
    data: {
      init: null
    },

    caption: {
      check: "String",
      init: "",
      event: "changeCaption"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "caption":
          control = new qx.ui.basic.Label("");
          this.bind("caption", control, "value");
          this.add(control);
          break;
        case "delete-button":
          control = new qx.ui.basic.Image("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAdVBMVEUAAACSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrWSkrX5qU1HAAAAJnRSTlMAAQIDBAUGBwgRFRYZGiEjQ3l7hYaqtLm8vsDFx87a4uvv8fP1+bbY9ZEAAACUSURBVBgZ7cELEoIgFAXQa5BFX0srjD5Udve/xHg6TjPAEjwHk9jmeURPn22J1LYjGwTakfcSMf1h0ADaMbggpjxFXTqKExLGU3wprELKeI6sQo7xHFiFvD173Rx52nFQI0s7jmpk6Bv/GiSKG4XdeYoDYkuKVsF4Bg8kKpJXBcB48r1CqmKrIIx/rZGzKDCYKUwiP90zFUbRdHbzAAAAAElFTkSuQmCC");
          control.set({
            scale: true,
            width: 20,
            height: 20
          });
          control.addListener("tap", () => this.fireEvent("deleteClicked"));
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __init: function() {
      this.setPaddingLeft(8);
      this.setPaddingRight(4);

      const d = new qx.ui.decoration.Decorator().set({
        backgroundColor: "material-button-background",
        radius: 4
      });
      this.set({
        decorator: d
      });

      this._createChildControl("caption");
      this._createChildControl("delete-button");
    }
  }
});
