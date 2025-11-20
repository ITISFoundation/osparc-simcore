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
    "conversationAdded": "qx.event.type.Data",
    "conversationCreated": "qx.event.type.Data",
    "conversationDeleted": "qx.event.type.Data",
  },

  statics: {
    TYPES: {
      SUPPORT: "SUPPORT",
      SUPPORT_CALL: "SUPPORT_CALL",
    },
  },

  members: {
    getConversations: function() {
      return Object.values(this.__conversationsCached);
    },

    fetchConversations: function() {
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
            const conversation = this.__addToCache(conversationData);
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
          const conversation = this.__addToCache(conversationData);
          return conversation;
        });
    },

    postConversation: function(extraContext = {}, type = osparc.store.ConversationsSupport.TYPES.SUPPORT) {
      const url = window.location.href;
      extraContext["deployment"] = url;
      extraContext["product"] = osparc.product.Utils.getProductName();
      const params = {
        data: {
          name: "null",
          type,
          extraContext,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "postConversation", params)
        .then(conversationData => {
          this.conversationCreated(conversationData);
          return conversationData;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    conversationCreated: function(conversationData) {
      const conversation = this.__addToCache(conversationData);
      this.fireDataEvent("conversationCreated", conversation);
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

    __patchConversation: function(conversationId, data) {
      const params = {
        url: {
          conversationId,
        },
        data,
      };
      return osparc.data.Resources.fetch("conversationsSupport", "patchConversation", params);
    },

    renameConversation: function(conversationId, name) {
      const patchData = {
        name,
      };
      return this.__patchConversation(conversationId, patchData);
    },

    patchExtraContext: function(conversationId, extraContext) {
      const patchData = {
        extraContext,
      };
      return this.__patchConversation(conversationId, patchData);
    },

    markAsRead: function(conversationId) {
      const patchData = {};
      if (osparc.store.Groups.getInstance().amIASupportUser()) {
        patchData["isReadBySupport"] = true;
      } else {
        patchData["isReadByUser"] = true;
      }
      return this.__patchConversation(conversationId, patchData);
    },

    markAsResolved: function(conversationId) {
      const patchData = {
        resolved: true,
      };
      return this.__patchConversation(conversationId, patchData);
    },

    fetchLastMessage: function(conversationId) {
      const params = {
        url: {
          conversationId,
          offset: 0,
          limit: 1,
        }
      };
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params, options);
    },

    fetchFirstMessage: function(conversationId, conversationPaginationMetadata) {
      const params = {
        url: {
          conversationId,
          offset: Math.max(0, conversationPaginationMetadata["total"] - 1),
          limit: 1,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params);
    },

    postMessage: function(conversationId, content) {
      const params = {
        url: {
          conversationId,
        },
        data: {
          content,
          "type": "MESSAGE",
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "postMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    editMessage: function(message, content) {
      const conversationId = message.getConversationId();
      const messageId = message.getMessageId();
      const params = {
        url: {
          conversationId,
          messageId,
        },
        data: {
          content,
        },
      };
      return osparc.data.Resources.fetch("conversationsSupport", "editMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteMessage: function(message) {
      const conversationId = message.getConversationId();
      const messageId = message.getMessageId();
      const params = {
        url: {
          conversationId,
          messageId,
        },
      };
      return osparc.data.Resources.fetch("conversationsSupport", "deleteMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __addToCache: function(conversationData) {
      // check if already cached
      if (conversationData["conversationId"] in this.__conversationsCached) {
        return this.__conversationsCached[conversationData["conversationId"]];
      }
      // add to cache
      const conversation = new osparc.data.model.ConversationSupport(conversationData);
      this.__conversationsCached[conversation.getConversationId()] = conversation;
      this.fireDataEvent("conversationAdded", conversation);
      return conversation;
    },
  }
});
