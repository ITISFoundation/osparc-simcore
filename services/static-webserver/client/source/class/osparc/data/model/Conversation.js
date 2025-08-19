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
 * Class that stores Conversation data.
 */

qx.Class.define("osparc.data.model.Conversation", {
  extend: qx.core.Object,

  /**
   * @param conversationData {Object} Object containing the serialized Conversation Data
   * */
  construct: function(conversationData) {
    this.base(arguments);

    this.set({
      conversationId: conversationData.conversationId,
      name: conversationData.name,
      userGroupId: conversationData.userGroupId,
      type: conversationData.type,
      created: new Date(conversationData.created),
      modified: new Date(conversationData.modified),
      projectId: conversationData.projectUuid || null,
      extraContent: conversationData.extraContent || null,
    });
  },

  properties: {
    conversationId: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeConversationId",
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeName",
    },

    userGroupId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeUserGroupId",
    },

    type: {
      check: [
        "PROJECT_STATIC",
        "PROJECT_ANNOTATION",
        "SUPPORT",
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

    projectId: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeProjectId",
    },

    extraContent: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeExtraContent",
    },

    messages: {
      check: "Array",
      nullable: false,
      init: null,
    },
  },

  statics: {
  },

  members: {
    addMessage: function(message) {
      const messages = this.getMessages() || [];
      messages.push(message);
      this.setMessages(messages);
    },
  },
});
