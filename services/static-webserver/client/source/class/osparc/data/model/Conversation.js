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
  type: "abstract",
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
      lastMessageCreatedAt: conversationData.lastMessageCreatedAt ? new Date(conversationData.lastMessageCreatedAt) : null
    });

    this.__messages = [];
    this.__listenToConversationMessageWS();
  },

  statics: {
    CHANNELS: {
      CONVERSATION_CREATED: "conversation:created",
      CONVERSATION_UPDATED: "conversation:updated",
      CONVERSATION_DELETED: "conversation:deleted",
      CONVERSATION_MESSAGE_CREATED: "conversation:message:created",
      CONVERSATION_MESSAGE_UPDATED: "conversation:message:updated",
      CONVERSATION_MESSAGE_DELETED: "conversation:message:deleted",
    },

    MAX_TITLE_LENGTH: 50,
    MAX_CONTENT_LENGTH: 4096,
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
      apply: "_applyName",
    },

    userGroupId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeUserGroupId",
    },

    type: {
      check: [
        "PROJECT_STATIC",     // osparc.store.ConversationsProject.TYPES.PROJECT_STATIC
        "PROJECT_ANNOTATION", // osparc.store.ConversationsProject.TYPES.PROJECT_ANNOTATION
        "SUPPORT",            // osparc.store.ConversationsSupport.TYPES.SUPPORT
        "SUPPORT_CALL",       // osparc.store.ConversationsSupport.TYPES.SUPPORT_CALL
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

    lastMessageCreatedAt: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeLastMessageCreatedAt",
    },
  },

  events: {
    "messageAdded": "qx.event.type.Data",
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
  },

  members: {
    __nextRequestParams: null,
    __messages: null,

    _applyName: function(name) {
      return;
    },

    __listenToConversationMessageWS: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      [
        this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED,
      ].forEach(eventName => {
        const eventHandler = messageData => {
          if (messageData) {
            const conversationId = messageData["conversationId"];
            if (conversationId === this.getConversationId()) {
              switch (eventName) {
                case this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED:
                  this._addMessage(messageData);
                  this.setLastMessageCreatedAt(new Date(messageData.created));
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED:
                  this._updateMessage(messageData);
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED:
                  this._deleteMessage(messageData);
                  break;
              }
            }
          }
        };
        socket.on(eventName, eventHandler, this);
      });
    },

    amIOwner: function() {
      return this.getUserGroupId() === osparc.auth.Data.getInstance().getGroupId();
    },

    getNextMessages: function() {
      const params = {
        url: {
          conversationId: this.getConversationId(),
          offset: 0,
          limit: 42
        }
      };
      const isProjectConversation = this instanceof osparc.data.model.ConversationProject;
      if (isProjectConversation) {
        params.url.studyId = this.getStudyId();
      }

      const nextRequestParams = this.__nextRequestParams;
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      const promise = isProjectConversation ?
        osparc.data.Resources.fetch("conversationsStudies", "getMessagesPage", params, options) :
        osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params, options);
      return promise
        .then(resp => {
          const messagesData = resp["data"];
          const markAsUnread = false;
          messagesData.forEach(messageData => this._addMessage(messageData, markAsUnread));
          this.__nextRequestParams = resp["_links"]["next"];
          return resp;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    renameConversation: function(newName) {
      osparc.store.ConversationsSupport.getInstance().renameConversation(this.getConversationId(), newName)
        .then(() => this.setName(newName))
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    getMessages: function() {
      return this.__messages;
    },

    getMessageIndex: function(messageId) {
      return this.__messages.findIndex(msg => msg.getMessageId() === messageId);
    },

    messageExists: function(messageId) {
      return this.__messages.some(msg => msg.getMessageId() === messageId);
    },

    _addMessage: function(messageData) {
      let message = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
      if (!message) {
        message = new osparc.data.model.Message(messageData);
        this.__messages.push(message);
        osparc.data.model.Message.sortMessagesByDate(this.__messages);
        this.fireDataEvent("messageAdded", message);
      }
      return message;
    },

    _updateMessage: function(messageData) {
      if (messageData) {
        const found = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
        if (found) {
          found.setData(messageData);
          this.fireDataEvent("messageUpdated", found);
        }
      }
    },

    _deleteMessage: function(messageData) {
      if (messageData) {
        const found = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
        if (found) {
          this.__messages.splice(this.__messages.indexOf(found), 1);
          this.fireDataEvent("messageDeleted", found);
        }
      }
    },
  },
});
