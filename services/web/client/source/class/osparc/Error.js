/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The Error page
 *
 * -----------------------
 * |  oSparc error logo  |
 * |   - status code     |
 * |   - error msg       |
 * -----------------------
 *
 */
qx.Class.define("osparc.Error", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();
  },

  properties: {
    code: {
      check: "String",
      init: "",
      nullable: true,
      apply: "_applyCode"
    },

    messages: {
      check: "Array",
      init: [],
      nullable: true,
      apply: "_applyMessages"
    }
  },

  members: {
    __status: null,
    __messages: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "logo": {
          control = new osparc.ui.basic.Logo();
          break;
        }
        case "logo-lying": {
          control = new qx.ui.basic.Image().set({
            source: "osparc/lyingpanda.png",
            scale: true,
            alignX: "center",
            width: 450,
            height: 300
          });
          break;
        }
        case "code": {
          control = new qx.ui.basic.Label().set({
            font: "text-18",
            alignX: "center",
            width: 200
          });
          break;
        }
        case "messages-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            maxWidth: 200
          });
          break;
        }
        case "message": {
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            maxWidth: 200
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const logo = this.getChildControl("logo");
      const image = this.getChildControl("logo-lying");
      const status = this.__status = this.getChildControl("code");
      const message = this.__messages = this.getChildControl("messages-layout");

      const errorWidget = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignY: "middle"
      }));
      errorWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      errorWidget.add(logo);
      errorWidget.add(image);
      errorWidget.add(status);
      errorWidget.add(message);
      errorWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });

      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(errorWidget);
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
    },

    _applyCode: function(status) {
      this.__status.setValue("Error: " + status);
    },

    _applyMessages: function(messages) {
      this.__messages.removeAll();
      messages.forEach(msg => {
        const message = this.getChildControl("message");
        message.set({
          value: msg.toString(),
          allowGrowX: true
        });
        this.__messages.add(message);
      });
    }
  }
});
