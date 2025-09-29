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


qx.Class.define("osparc.support.ConversationsPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.getChildControl("conversations-list");
    this.getChildControl("ask-a-question-button");
    this.getChildControl("book-a-call-button");
    if (osparc.product.Utils.isBookACallEnabled()) {
      this.getChildControl("book-a-call-button-3rd");
    }
  },

  events: {
    "openConversation": "qx.event.type.Data",
    "createConversation": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversations-list": {
          control = new osparc.support.Conversations();
          control.addListener("openConversation", e => {
            const conversationId = e.getData();
            this.fireDataEvent("openConversation", conversationId);
          }, this);
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this._add(scroll, {
            flex: 1,
          });
          break;
        }
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(15).set({
            alignX: "center",
          }));
          this._add(control);
          break;
        case "ask-a-question-button":
          control = new qx.ui.form.Button(this.tr("Ask a Question"), "@FontAwesome5Solid/comments/14").set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION), this);
          this.getChildControl("buttons-layout").add(control);
          break;
        case "book-a-call-button":
          control = new qx.ui.form.Button(this.tr("Book a Call"), "@FontAwesome5Solid/phone/14").set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL), this);
          this.getChildControl("buttons-layout").add(control);
          break;
        case "book-a-call-button-3rd":
          control = new qx.ui.form.Button(this.tr("Book a Call"), "@FontAwesome5Solid/flask/14").set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL_3RD), this);
          this.getChildControl("buttons-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
