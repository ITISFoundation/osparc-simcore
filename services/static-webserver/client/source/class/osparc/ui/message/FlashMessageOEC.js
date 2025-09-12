/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.message.FlashMessageOEC", {
  extend: osparc.ui.message.FlashMessage,

  /**
   * Constructor for the FlashMessage.
   *
   * @param {String} message Message that the user will read.
   * @param {Number} duration
   * @param {String} supportId
   */
  construct: function(message, duration, supportId) {
    this.base(arguments, message, "ERROR", duration ? duration*2 : null);

    if (osparc.store.Groups.getInstance().isSupportEnabled() && false) {
      this.getChildControl("contact-support");
    } else {
      const oecAtom = this.getChildControl("oec-atom");
      this.bind("supportId", oecAtom, "label");
    }
    if (supportId) {
      this.setSupportId(supportId);
    }
  },

  properties: {
    supportId: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeSupportId",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "oec-atom":
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/copy/10",
            iconPosition: "right",
            gap: 8,
            cursor: "pointer",
            alignX: "center",
            allowGrowX: false,
          });
          control.addListener("tap", () => this.__copyToClipboard());
          this.addWidget(control);
          break;
        case "contact-support":
          control = new qx.ui.basic.Atom().set({
            label: this.tr("Contact Support"),
            icon: "@FontAwesome5Solid/comments/10",
            iconPosition: "left",
            gap: 8,
            cursor: "pointer",
            alignX: "center",
            allowGrowX: false,
          });
          control.addListener("tap", () => this.__openSupportChat());
          this.addWidget(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __getContext: function() {
      const dataToClipboard = {
        message: this.getMessage(),
        supportId: this.getSupportId(),
        timestamp: new Date().toString(),
        url: window.location.href,
        releaseTag: osparc.utils.Utils.getReleaseTag(),
      }
      if (osparc.store.Store.getInstance().getCurrentStudy()) {
        dataToClipboard["projectId"] = osparc.store.Store.getInstance().getCurrentStudy().getUuid();
      }
      return osparc.utils.Utils.prettifyJson(dataToClipboard);
    },

    __getSupportFriendlyContext: function() {
      let curatedText = "Extra Context:";
      curatedText += "\nError: " + this.getMessage();
      curatedText += "\nSupportID: " + this.getSupportId();
      curatedText += "\nTimestamp: " + new Date().toISOString();
      curatedText += "\nURL: " + window.location.href;
      curatedText += "\nRelease Tag: " + osparc.utils.Utils.getReleaseTag();
      if (osparc.store.Store.getInstance().getCurrentStudy()) {
        curatedText += "\nProject ID: " + osparc.store.Store.getInstance().getCurrentStudy().getUuid();
      }
      return curatedText;
    },

    __copyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.__getContext());
    },

    __openSupportChat: function() {
      const supportCenter = osparc.support.SupportCenter.openWindow();
      supportCenter.createConversation("reportOEC");

      const textToAddMessageField = msg => {
        if (supportCenter.getChildControl("conversation-page")) {
          supportCenter.getChildControl("conversation-page").postMessage(msg);
        }
      }

      const caption = this.tr("Something went wrong");
      const introText = this.tr("Please describe what you were doing before the error (optional).\nThis will help our support team understand the context and resolve the issue faster.");
      const confirmationWindow = new osparc.ui.window.Confirmation(introText);
      confirmationWindow.setCaption(caption);
      confirmationWindow.getChildControl("message-label").setFont("text-13");
      const extraContextTA = new qx.ui.form.TextArea().set({
        font: "text-13",
        autoSize: true,
        minHeight: 70,
        maxHeight: 140
      });
      confirmationWindow.addWidget(extraContextTA);
      confirmationWindow.addCancelButton();
      confirmationWindow.setConfirmText(this.tr("Send Report"));
      confirmationWindow.open();
      confirmationWindow.addListener("close", () => {
        if (confirmationWindow.getConfirmed()) {
          const extraContext = extraContextTA.getValue()
          const friendlyContext = this.__getSupportFriendlyContext();
          const text = "Dear Support Team,\n" + extraContext + "\n" + friendlyContext;
          textToAddMessageField(text);
          // This should be an automatic response in the chat
          const msg = this.tr("Thanks, your report has been sent.<br>Our support team will get back to you.");
          osparc.FlashMessenger.logAs(msg, "INFO");
        } else {
          supportCenter.close();
        }
      });
    },
  }
});
