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

/**
 * Class that stores Message data.
 */

qx.Class.define("osparc.data.model.Message", {
  extend: qx.core.Object,

  /**
   * @param messageData {Object} Object containing the serialized Message Data
   * */
  construct: function(messageData) {
    this.base(arguments);

    this.setData(messageData);
  },

  properties: {
    messageId: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeMessageId",
    },

    conversationId: {
      check: "String",
      nullable: true, // system messages have null conversationId
      init: null,
      event: "changeConversationId",
    },

    userGroupId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeUserGroupId",
    },

    content: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeContent",
    },

    type: {
      check: [
        "MESSAGE",
        "NOTIFICATION",
      ],
      nullable: false,
      init: null,
      event: "changeType",
    },

    created: {
      check: "Date",
      nullable: false,
      init: null,
      event: "changeCreated",
    },

    modified: {
      check: "Date",
      nullable: false,
      init: null,
      event: "changeModified",
    },
  },

  statics: {
    SYSTEM_MESSAGE_ID: -1,

    sortMessagesByDate: function(messages) {
      // oldest first: higher in the list. Latest at the bottom
      messages.sort((a, b) => a.getCreated() - b.getCreated());
    },

    isSupportMessage: function(message) {
      return message.getUserGroupId() === osparc.data.model.Message.SYSTEM_MESSAGE_ID;
    },

    isMyMessage: function(message) {
      if (osparc.data.model.Message.isSupportMessage(message)) {
        return false;
      }
      return message && osparc.auth.Data.getInstance().getGroupId() === message.getUserGroupId();
    },
  },

  members: {
    setData: function(messageData) {
      this.set({
        messageId: messageData.messageId,
        conversationId: messageData.conversationId,
        content: messageData.content,
        userGroupId: messageData.userGroupId,
        created: new Date(messageData.created),
        modified: new Date(messageData.modified),
        type: messageData.type,
      });
    },
  }
});
