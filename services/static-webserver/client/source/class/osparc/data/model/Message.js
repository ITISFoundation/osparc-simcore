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
  construct: function(messageData, studyId) {
    this.base(arguments);

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
});
