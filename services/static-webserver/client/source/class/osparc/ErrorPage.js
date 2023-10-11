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
 * |    oSparc logo      |
 * |       panda         |
 * |   - status code     |
 * |   - error msgs      |
 * |   action buttons    |
 * -----------------------
 *
 */
qx.Class.define("osparc.ErrorPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(20, 20);
    layout.setColumnFlex(0, 1);
    layout.setColumnMinWidth(1, 400);
    layout.setColumnFlex(2, 1);
    layout.setRowFlex(this.self().POS.MESSAGES, 1);
    this._setLayout(layout);

    this._add(new qx.ui.core.Spacer(), {
      column: 0,
      row: 0
    });
    this._add(new qx.ui.core.Spacer(), {
      column: 2,
      row: 0
    });

    this.getChildControl("logo");
    this.getChildControl("lying-panda");
    this.getChildControl("code");
    this.getChildControl("messages-layout");
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
    },

    POS: {
      LOGO: 0,
      PANDA: 1,
      ERROR: 3,
      MESSAGES: 4,
      ACTIONS: 5
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "logo":
          control = new osparc.ui.basic.Logo().set({
            width: 130,
            height: 55
          });
          this._add(control, {
            column: 1,
            row: this.self().POS.LOGO
          });
          break;
        case "lying-panda":
          control = new qx.ui.basic.Image().set({
            source: "osparc/lyingpanda.png",
            scale: true,
            alignX: "center",
            width: 300,
            height: 200
          });
          this._add(control, {
            column: 1,
            row: this.self().POS.PANDA
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
              const errorText = this.tr("Error: ");
              if (code in this.self().FRIENDLY_HTTP_STATUS) {
                return errorText + this.self().FRIENDLY_HTTP_STATUS[code];
              }
              return errorText + code;
            }
          });
          this._add(control, {
            column: 1,
            row: this.self().POS.ERROR
          });
          break;
        case "messages-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            maxWidth: 400
          });
          this._add(control, {
            column: 1,
            row: this.self().POS.MESSAGES
          });
          break;
        case "actions-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(20)).set({
            alignX: "center",
            maxWidth: 400
          });
          break;
        case "copy-to-clipboard": {
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/copy/14",
            label: this.tr("Copy to clipboard")
          });
          control.addListener("execute", () => this.__copyMessagesToClipboard(), this);
          break;
        }
        case "support-email": {
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/envelope/14",
            label: this.tr("Support email")
          });
          control.addListener("execute", () => this.__supportEmail(), this);
          const actionsLayout = this.getChildControl("actions-layout");
          actionsLayout.add(control, {
            flex: 1
          });
          break;
        }
        case "log-in-button": {
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/sign-in-alt/14",
            label: this.tr("Log in"),
            appearance: "strong-button",
            center: true
          });
          control.addListener("execute", () => this.__logIn(), this);
          const actionsLayout = this.getChildControl("actions-layout");
          actionsLayout.add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __createMessage: function(text) {
      const message = new qx.ui.basic.Label(text).set({
        font: "text-16",
        selectable: true,
        rich: true,
        wrap: true
      });
      return message;
    },

    __applyMessages: function(messages) {
      const messagesLayout = this.getChildControl("messages-layout");
      messagesLayout.removeAll();
      messages.forEach(msg => {
        const message = this.__createMessage(msg.toString());
        messagesLayout.add(message);
      });

      const actionsLayout = this.getChildControl("actions-layout");
      messagesLayout.add(actionsLayout);

      const logIn = this.getChildControl("log-in-button");
      actionsLayout.add(logIn, {
        flex: 1
      });
      const supportEmail = this.getChildControl("support-email");
      actionsLayout.add(supportEmail, {
        flex: 1
      });
      const copyToClipboard = this.getChildControl("copy-to-clipboard");
      actionsLayout.add(copyToClipboard, {
        flex: 1
      });
    },

    __copyMessagesToClipboard: function() {
      let text = "";
      this.getMessages().forEach(msg => text+= msg);
      osparc.utils.Utils.copyTextToClipboard(text);
    },

    __supportEmail: function() {
      const supportEmail = osparc.store.VendorInfo.getInstance().getSupportEmail();
      const giveEmailFeedbackWindow = new osparc.ui.window.Dialog("Support", null, qx.locale.Manager.tr("Please send us an email to:"));
      const mailto = osparc.store.Support.getMailToLabel(supportEmail, "Access error");
      giveEmailFeedbackWindow.addWidget(mailto);
      giveEmailFeedbackWindow.open();
    },

    __logIn: function() {
      window.location.reload();
    }
  }
});
