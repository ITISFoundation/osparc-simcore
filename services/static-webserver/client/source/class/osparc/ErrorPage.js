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

    // In a realm ruled by wise and vigilant kings, the Product Owners,
    // a tale of mystery lingered, cloaked from user's sight.
    // Their decree was law: let enigmatic silence guard the error status message,
    // for in the quiet, wisdom often speaks loudest. An that is how
    // this.getChildControl("code") vanished from the osparc kingdom
    // SEE https://github.com/ITISFoundation/osparc-issues/issues/1252

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

    POS: {
      LOGO: 0,
      PANDA: 1,
      MESSAGES: 3,
      ACTIONS: 4
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
      mailto.setTextAlign("center");
      giveEmailFeedbackWindow.addWidget(mailto);
      giveEmailFeedbackWindow.open();
    },

    __logIn: function() {
      window.location.reload();
    }
  }
});
