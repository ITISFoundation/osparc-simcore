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
      const conversationId = conversation.getConversationId();
      osparc.store.ConversationsSupport.getInstance().getLastMessage(conversationId)
        .then(lastMessages => {
          if (lastMessages && lastMessages.length) {
            // decorate
            this.getChildControl("thumbnail").getContentElement().setStyles({
              "border-radius": "16px"
            });
            this.getChildControl("subtitle").set({
              textColor: "text-disabled",
            });
            const lastMessage = lastMessages[0];
            const date = osparc.utils.Utils.formatDateAndTime(new Date(lastMessage.created));
            const name = conversation.getName();
            this.set({
              title: name && name !== "null" ? name : lastMessage.content,
              subtitle: date,
            });

            const userGroupId = lastMessage.userGroupId;
            osparc.store.Users.getInstance().getUser(userGroupId)
              .then(user => {
                if (user) {
                  this.set({
                    thumbnail: user.getThumbnail(),
                    subtitle: user.getLabel() + " - " + date,
                  });
                }
              });
          }
        });
    },
  }
});
