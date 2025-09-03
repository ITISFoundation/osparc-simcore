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

    if (osparc.product.Utils.isSupportEnabled()) {
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
      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      const dataToClipboard = {
        message: this.getMessage(),
        supportId: this.getSupportId(),
        timestamp: new Date().toString(),
        url: window.location.href,
        releaseTag: osparc.utils.Utils.getReleaseTag(),
        studyId: currentStudy ? currentStudy.getUuid() : "",
      }
      return osparc.utils.Utils.prettifyJson(dataToClipboard);
    },

    __copyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.__getContext());
    },

    __openSupportChat: function() {
      const caption = this.tr("Something went wrong");
      const introText = this.tr("Please describe what you were doing before the error (optional).\nThis will help our support team understand the context and resolve the issue faster.");
      const dialog = new osparc.ui.window.Confirmation(introText);
      dialog.setCaption(caption);
      dialog.getChildControl("message-label").setFont("text-13");
      const extraContext = new qx.ui.form.TextArea().set({
        font: "text-13",
        autoSize: true,
        minHeight: 70,
        maxHeight: 140
      });
      dialog.addWidget(extraContext);
      dialog.addCancelButton();
      dialog.setConfirmText(this.tr("Send Report"));
      dialog.open();

      const supportCenter = osparc.support.SupportCenter.openWindow();
      supportCenter.openConversation(null);

      /*
      if (
        supportCenter.getChildControl("conversation-page") &&
        supportCenter.getChildControl("conversation-page").getChildControl("conversation-content") &&
        supportCenter.getChildControl("conversation-page").getChildControl("conversation-content").getChildControl("add-message") &&
        supportCenter.getChildControl("conversation-page").getChildControl("conversation-content").getChildControl("add-message").getChildControl("comment-field")
      ) {
        supportCenter.getChildControl("conversation-page").getChildControl("conversation-content").getChildControl("add-message").getChildControl("comment-field").setText(this.__getContext());
      }
      */
    },
  }
});
