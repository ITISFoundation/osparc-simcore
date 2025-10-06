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

qx.Class.define("osparc.support.ConversationListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setSpacingY(0);

    // decorate
    this.getChildControl("thumbnail").setDecorator("circled");
    this.getChildControl("title").set({
      rich: false, // let ellipsis work
    });
    this.getChildControl("subtitle").set({
      // textColor: "text-disabled",
      rich: false, // let ellipsis work
    });
    this.getChildControl("sub-subtitle").set({
      textColor: "text-disabled",
    });
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: false,
      event: "changeConversation",
      apply: "__applyConversation",
    },
  },

  members: {
    __applyConversation: function(conversation) {
      conversation.bind("nameAlias", this, "title");

      this.__populateWithLastMessage();
      conversation.addListener("changeLastMessage", this.__populateWithLastMessage, this);

      this.__populateWithFirstMessage();
      conversation.addListener("changeFirstMessage", this.__populateWithFirstMessage, this);
    },

    __populateWithLastMessage: function() {
      const conversation = this.getConversation();
      const lastMessage = conversation.getLastMessage();
      if (lastMessage) {
        const date = osparc.utils.Utils.formatDateAndTime(new Date(lastMessage.created));
        this.set({
          role: date,
        });
        const userGroupId = lastMessage.userGroupId;
        osparc.store.Users.getInstance().getUser(userGroupId)
          .then(user => {
            if (user) {
              this.set({
                thumbnail: user.getThumbnail(),
                subtitle: user.getLabel() + ": " + lastMessage["content"],
              });
            }
          });
      }
    },

    __populateWithFirstMessage: function() {
      const conversation = this.getConversation();
      const firstMessage = conversation.getFirstMessage();
      if (firstMessage) {
        const userGroupId = firstMessage.userGroupId;
        osparc.store.Users.getInstance().getUser(userGroupId)
          .then(user => {
            if (user) {
              const amISupporter = osparc.store.Groups.getInstance().amIASupportUser();
              let subSubtitle = "Started";
              if (amISupporter) {
                subSubtitle += " by " + user.getLabel();
              }
              const date = osparc.utils.Utils.formatDateAndTime(new Date(firstMessage.created));
              subSubtitle += " on " + date;
              this.set({
                subSubtitle,
              });
            }
          });
      }
    },
  },
});
