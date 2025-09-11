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

    this.getChildControl("conversations-intro-text");
    this.getChildControl("conversations-list");
    this.getChildControl("ask-a-question-button");
    this.getChildControl("book-a-call-button");
  },

  events: {
    "openConversation": "qx.event.type.Data",
    "createConversationBookCall": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversations-intro-text": {
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-14",
          });
          const isSupportUser = osparc.store.Groups.getInstance().amIASupportUser();
          control.set({
            value: isSupportUser ?
              this.tr("Thanks for being here! Let's help every user feel supported.") :
              this.tr("Need help or want to share feedback? You're in the right place."),
          });
          this._add(control);
          break;
        }
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
          control.addListener("execute", () => this.fireDataEvent("openConversation", null), this);
          this.getChildControl("buttons-layout").add(control);
          break;
        case "book-a-call-button":
          control = new qx.ui.form.Button(this.tr("Book a Call"), "@FontAwesome5Solid/phone/14").set({
            appearance: "strong-button",
            allowGrowX: false,
            center: true,
          });
          control.addListener("execute", () => this.fireEvent("createConversationBookCall"), this);
          this.getChildControl("buttons-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
