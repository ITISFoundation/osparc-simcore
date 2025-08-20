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


qx.Class.define("osparc.support.ConversationPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-button");

    const conversation = this.getChildControl("conversation");
    this.bind("conversationId", conversation, "conversationId");
    conversation.bind("conversationId", this, "conversationId");
  },

  properties: {
    conversationId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeConversationId",
      apply: "__applyConversationId",
    },
  },

  events: {
    "showConversations": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversation-header-layout": {
          const headerGrid = new qx.ui.layout.Grid(5, 5);
          headerGrid.setColumnAlign(0, "center", "middle");
          headerGrid.setColumnFlex(1, 1);
          headerGrid.setColumnAlign(2, "center", "middle");
          control = new qx.ui.container.Composite(headerGrid).set({
            padding: 5,
          });
          this._add(control);
          break;
        }
        case "back-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Return to Messages"),
            icon: "@FontAwesome5Solid/arrow-left/16",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.fireEvent("showConversations"));
          this.getChildControl("conversation-header-layout").add(control, {
            row: 0,
            column: 0,
            rowSpan: 2,
          });
          break;
        case "conversation-title":
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            allowGrowX: true,
            });
            this.getChildControl("conversation-header-layout").add(control, {
              row: 0,
              column: 1,
            });
          break;
        case "conversation-options":
          control = new qx.ui.form.MenuButton().set({
            maxWidth: 22,
            maxHeight: 22,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/14",
          });
          this.getChildControl("conversation-header-layout").add(control, {
            row: 0,
            column: 2,
            rowSpan: 2,
          });
          break;
        case "conversation-extra-content":
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            allowGrowX: true,
          });
          this.getChildControl("conversation-header-layout").add(control, {
            row: 1,
            column: 1,
          });
          break;
        case "conversation":
          control = new osparc.support.Conversation();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this._add(scroll, {
            flex: 1,
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyConversationId: function(conversationId) {
      const title = this.getChildControl("conversation-title");
      const options = this.getChildControl("conversation-options");
      if (conversationId) {
        osparc.store.ConversationsSupport.getInstance().getConversation(conversationId)
          .then(conversation => {
            const name = conversation.getName();
            if (name && name !== "null") {
              title.setValue(name);
            } else {
              osparc.store.ConversationsSupport.getInstance().getLastMessage(conversationId)
                .then(lastMessage => {
                  title.setValue(lastMessage ? lastMessage.content : "");
                });
            }
            options.show();
            const amISupporter = osparc.store.Products.getInstance().amIASupportUser();
            const extraContextLabel = this.getChildControl("conversation-extra-content");
            extraContextLabel.setVisibility(amISupporter ? "visible" : "excluded");
            const extraContext = conversation.getExtraContext();
            if (amISupporter && extraContext && Object.keys(extraContext).length) {
              let extraContext = "";
              extraContext += `ID: ${conversationId}<br>`;
              if ("projectId" in extraContext) {
                extraContext += `Project ID: ${extraContext["projectId"]}<br>`;
              }
              extraContextLabel.setValue(extraContext);
            }
          });
      } else {
        title.setValue("");
        options.exclude();
      }
    }
  }
});
