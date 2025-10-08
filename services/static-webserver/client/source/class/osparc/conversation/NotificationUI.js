/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.conversation.NotificationUI", {
  extend: osparc.conversation.MessageUI,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "notification-content":
          control = new qx.ui.basic.Label().set({
            paddingTop: 5,
            paddingBottom: 5,
          });
          this.getChildControl("main-layout").addAt(control, 2);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyMessage: function(message) {
      this.base(arguments, message);

      this.getChildControl("menu-button").hide();
      this.getChildControl("message-bubble").exclude();

      const isMyMessage = osparc.conversation.MessageUI.isMyMessage(message);

      let msgContent = "🔔 ";
      const messageContent = this.getChildControl("notification-content");
      const notifierUserGroupId = parseInt(message.getUserGroupId());
      const notifiedUserGroupId = parseInt(message.getContent());
      Promise.all([
        osparc.store.Users.getInstance().getUser(notifierUserGroupId),
        osparc.store.Users.getInstance().getUser(notifiedUserGroupId),
      ])
        .then(values => {
          const notifierUser = values[0];
          if (isMyMessage) {
            msgContent += "You";
          } else if (notifierUser) {
            msgContent += notifierUser.getLabel();
          } else {
            msgContent += "unknown user";
          }

          msgContent += " notified ";

          const notifiedUser = values[1];
          if (osparc.auth.Data.getInstance().getGroupId() === notifiedUserGroupId) {
            msgContent += "You";
          } else if (notifiedUser) {
            msgContent += notifiedUser.getLabel();
          } else {
            msgContent += "unknown user";
          }
        })
        .catch(() => {
          msgContent += "unknown user notified";
        })
        .finally(() => {
          messageContent.setValue(msgContent);
        });
    }
  }
});
