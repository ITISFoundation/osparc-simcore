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

qx.Class.define("osparc.store.ConversationsSupport", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__conversationsCached = {};
  },

  events: {
    "conversationDeleted": "qx.event.type.Data",
  },

  statics: {
    TYPES: {
      SUPPORT: "SUPPORT",
    },
  },

  members: {
    getConversations: function() {
      const params = {
        url: {
          offset: 0,
          limit: 42,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getConversationsPage", params)
        .then(conversationsData => {
          const conversations = [];
          if (conversationsData.length) {
            // Sort conversations by created date, newest first (the new ones will be next to the plus button)
            conversationsData.sort((a, b) => new Date(b["created"]) - new Date(a["created"]));
          }
          conversationsData.forEach(conversationData => {
            const conversation = new osparc.data.model.Conversation(conversationData);
            this.__addToCache(conversation);
            conversations.push(conversation);
          });
          return conversations;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    getConversation: function(conversationId) {
      if (conversationId in this.__conversationsCached) {
        return Promise.resolve(this.__conversationsCached[conversationId]);
      }

      const params = {
        url: {
          conversationId,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getConversation", params)
        .then(conversationData => {
          const conversation = new osparc.data.model.Conversation(conversationData);
          this.__addToCache(conversation);
          return conversation;
        });
    },

    addConversation: function(extraContext = {}) {
      const url = window.location.href;
      extraContext["deployment"] = url;
      extraContext["product"] = osparc.product.Utils.getProductName();
      const params = {
        data: {
          name: "null",
          type: osparc.store.ConversationsSupport.TYPES.SUPPORT,
          extraContext,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "addConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteConversation: function(conversationId) {
      const params = {
        url: {
          conversationId,
        },
      };
      return osparc.data.Resources.fetch("conversationsSupport", "deleteConversation", params)
        .then(() => {
          this.fireDataEvent("conversationDeleted", {
            conversationId,
          })
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    renameConversation: function(conversationId, name) {
      const params = {
        url: {
          conversationId,
        },
        data: {
          name,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "renameConversation", params);
    },

    getLastMessage: function(conversationId) {
      if (
        conversationId in this.__conversationsCached &&
        this.__conversationsCached[conversationId].getMessages() &&
        this.__conversationsCached[conversationId].getMessages().length
      ) {
        return Promise.resolve(this.__conversationsCached[conversationId].getMessages()[0]);
      }

      const params = {
        url: {
          conversationId,
          offset: 0,
          limit: 1,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params)
        .then(messagesData => {
          if (messagesData && messagesData.length) {
            const lastMessage = messagesData[0];
            this.__addMessageToCache(conversationId, lastMessage);
            return lastMessage;
          }
          return lastMessage;
        });
    },

    addMessage: function(conversationId, message) {
      const params = {
        url: {
          conversationId,
        },
        data: {
          "content": message,
          "type": "MESSAGE",
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "addMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    editMessage: function(conversationId, messageId, message) {
      const params = {
        url: {
          conversationId,
          messageId,
        },
        data: {
          "content": message,
        },
      };
      return osparc.data.Resources.fetch("conversationsSupport", "editMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteMessage: function(message) {
      const params = {
        url: {
          conversationId: message["conversationId"],
          messageId: message["messageId"],
        },
      };
      return osparc.data.Resources.fetch("conversationsSupport", "deleteMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __addToCache: function(conversation) {
      this.__conversationsCached[conversation.getConversationId()] = conversation;
    },

    __addMessageToCache: function(conversationId, messageData) {
      if (conversationId in this.__conversationsCached) {
        this.__conversationsCached[conversationId].addMessage(messageData);
      }
    },
  }
});
