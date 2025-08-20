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
      extraContext: conversationData.extraContext || null,
    });

    this.__fetchLastMessage();
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
      apply: "__applyName",
    },

    nameAlias: {
      check: "String",
      nullable: false,
      init: "",
      event: "changeNameAlias",
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

    extraContext: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeExtraContext",
    },

    messages: {
      check: "Array",
      nullable: false,
      init: null,
      apply: "__applyMessages",
    },
  },

  members: {
    __fetchLastMessagePromise: null,

    __applyName: function(name) {
      if (name && name !== "null") {
        this.setNameAlias(name);
      }
    },

    __applyMessages: function(messages) {
      console.log(messages);
    },

    __fetchLastMessage: function() {
      if (this.__fetchLastMessagePromise) {
        return this.__fetchLastMessagePromise;
      }

      let promise = osparc.store.ConversationsSupport.getInstance().getLastMessage(this.getConversationId());
      promise
        .then(lastMessage => {
          this.setNameAlias(lastMessage ? lastMessage.content : "");
          promise = null;
          return lastMessage;
        })
        .finally(() => {
          this.__fetchLastMessagePromise = null;
        });

      this.__fetchLastMessagePromise = promise;
      return promise;
    },

    getLastMessage: function() {
      if (this.getMessages() && this.getMessages().length) {
        return Promise.resolve(this.getMessages()[0]);
      }
      return this.__fetchLastMessage();
    },

    renameConversation: function(newName) {
      osparc.store.ConversationsSupport.getInstance().renameConversation(this.getConversationId(), newName)
        .then(() => {
          this.setNameAlias(newName);
        });
    },

    addMessage: function(message) {
      const messages = this.getMessages() || [];
      messages.push(message);
      this.setMessages(messages);
    },

    getContextProjectId: function() {
      if (this.getExtraContext() && "projectId" in this.getExtraContext()) {
        return this.getExtraContext()["projectId"];
      }
      return null;
    }
  },
});
