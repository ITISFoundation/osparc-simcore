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
      nullable: false,
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
    sortMessagesByDate: function(messages) {
      // latest first
      messages.sort((a, b) => new Date(b.getCreated()) - new Date(a.getCreated()));
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
