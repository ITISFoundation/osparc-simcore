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
    layout.setSpacingY(4);

    this.setMinHeight(32);
  },

  properties: {
    conversationId: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeConversationId",
      apply: "__applyConversationId",
    },
  },

  members: {
    __applyConversationId: function(conversationId) {
      osparc.store.ConversationsSupport.getInstance().getLastMessage(conversationId)
        .then(lastMessages => {
          if (lastMessages && lastMessages.length) {
            this.getChildControl("thumbnail").getContentElement().setStyles({
              "border-radius": "16px"
            });
            const lastMessage = lastMessages[0];
            const date = osparc.utils.Utils.formatDateAndTime(new Date(lastMessage.created));
            this.set({
              title: lastMessage.content,
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
