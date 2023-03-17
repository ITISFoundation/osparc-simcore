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
 * |   - error msgs       |
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
      event: "changeCode"
    },

    messages: {
      check: "Array",
      init: [],
      nullable: true,
      apply: "__applyMessages"
    }
  },

  statics: {
    FRIENDLY_HTTP_STATUS: {
      "200": "OK",
      "201": "Created",
      "202": "Accepted",
      "203": "Non-Authoritative Information",
      "204": "No Content",
      "205": "Reset Content",
      "206": "Partial Content",
      "300": "Multiple Choices",
      "301": "Moved Permanently",
      "302": "Found",
      "303": "See Other",
      "304": "Not Modified",
      "305": "Use Proxy",
      "306": "Unused",
      "307": "Temporary Redirect",
      "400": "Bad Request",
      "401": "Unauthorized",
      "402": "Payment Required",
      "403": "Forbidden",
      "404": "Not Found",
      "405": "Method Not Allowed",
      "406": "Not Acceptable",
      "407": "Proxy Authentication Required",
      "408": "Request Timeout",
      "409": "Conflict",
      "410": "Gone",
      "411": "Length Required",
      "412": "Precondition Required",
      "413": "Request Entry Too Large",
      "414": "Request-URI Too Long",
      "415": "Unsupported Media Type",
      "416": "Requested Range Not Satisfiable",
      "417": "Expectation Failed",
      "418": "I'm a teapot",
      "429": "Too Many Requests",
      "500": "Internal Server Error",
      "501": "Not Implemented",
      "502": "Bad Gateway",
      "503": "Service Unavailable",
      "504": "Gateway Timeout",
      "505": "HTTP Version Not Supported"
    }
  },

  members: {
    __messages: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "logo":
          control = new osparc.ui.basic.Logo();
          break;
        case "lying-panda":
          control = new qx.ui.basic.Image().set({
            source: "osparc/lyingpanda.png",
            scale: true,
            alignX: "center",
            width: 450,
            height: 300
          });
          break;
        case "code":
          control = new qx.ui.basic.Label().set({
            font: "text-18",
            alignX: "center",
            selectable: true,
            rich : true,
            width: 400
          });
          this.bind("code", control, "value", {
            converter: code => {
              if (code in this.self().FRIENDLY_HTTP_STATUS) {
                return this.tr("Error: ") + this.self().FRIENDLY_HTTP_STATUS[code];
              }
              return code;
            }
          });
          break;
        case "messages-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            maxWidth: 400
          });
          break;
        case "message":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            selectable: true,
            rich : true,
            width: 400
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const logo = this.getChildControl("logo");
      const image = this.getChildControl("lying-panda");
      const status = this.getChildControl("code");
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
      this._add(errorWidget, {
        flex: 1
      });
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
    },

    __applyMessages: function(messages) {
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
