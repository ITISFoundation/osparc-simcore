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
    __conversationsCached: null,

    init: function() {
      this.fetchConversations();
      this.listenToWS();
    },

    getConversations: function() {
      return Object.values(this.__conversationsCached);
    },

    listenToWS: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const types = Object.values(osparc.store.ConversationsSupport.TYPES);
      [
        osparc.data.model.Conversation.CHANNELS.CONVERSATION_CREATED,
        osparc.data.model.Conversation.CHANNELS.CONVERSATION_UPDATED,
        osparc.data.model.Conversation.CHANNELS.CONVERSATION_DELETED,
      ].forEach(eventName => {
        const eventHandler = conversationData => {
          if (conversationData && types.includes(conversationData["type"])) {
            switch (eventName) {
              case osparc.data.model.Conversation.CHANNELS.CONVERSATION_CREATED:
                const conversation = this.__addToCache(conversationData);
                this.fireDataEvent("conversationCreated", conversation);
                break;
              case osparc.data.model.Conversation.CHANNELS.CONVERSATION_UPDATED:
                this.__updateConversation(conversationData);
                break;
              case osparc.data.model.Conversation.CHANNELS.CONVERSATION_DELETED:
                this.__removeFromCache(conversationData["conversationId"]);
                this.fireDataEvent("conversationDeleted", {
                  conversationId: conversationData["conversationId"],
                });
                break;
            }
          }
        };
        socket.on(eventName, eventHandler, this);
      });
    },

    fetchConversations: function(filter, offset = 0) {
      const params = {
        url: {
          offset,
          limit: 9,
        }
      };
      let endpoint;
      switch (filter) {
        case "unread":
          if (osparc.store.Groups.getInstance().amIASupportUser()) {
            endpoint = "getConversationsPageUnreadBySupport";
          } else {
            endpoint = "getConversationsPageUnreadByUser";
          }
          break;
        case "active":
          endpoint = "getConversationsPageByStatus";
          params.url["status"] = "ACTIVE";
          break;
        case "archived":
          endpoint = "getConversationsPageByStatus";
          params.url["status"] = "ARCHIVED";
          break;
        case "all":
        default:
          endpoint = "getConversationsPage";
          break;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("conversationsSupport", endpoint, params, options)
        .then(resp => {
          const conversations = [];
          const conversationsData = resp["data"] || resp;
          const total = resp["_meta"] ? resp["_meta"]["total"] : null;
          if (Array.isArray(conversationsData)) {
            conversationsData.forEach(conversationData => {
              const conversation = this.__addToCache(conversationData);
              conversations.push(conversation);
            });
          }
          return { conversations, total };
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchConversationCount: function(filter) {
      const params = {
        url: {
          offset: 0,
          limit: 1,
        }
      };
      const options = {
        resolveWResponse: true
      };
      let endpoint;
      switch (filter) {
        case "unread":
          if (osparc.store.Groups.getInstance().amIASupportUser()) {
            endpoint = "getConversationsPageUnreadBySupport";
          } else {
            endpoint = "getConversationsPageUnreadByUser";
          }
          break;
        case "active":
          endpoint = "getConversationsPageByStatus";
          params.url["status"] = "ACTIVE";
          break;
        case "archived":
          endpoint = "getConversationsPageByStatus";
          params.url["status"] = "ARCHIVED";
          break;
        case "all":
        default:
          endpoint = "getConversationsPage";
          break;
      }
      return osparc.data.Resources.fetch("conversationsSupport", endpoint, params, options)
        .then(resp => resp["_meta"]["total"])
        .catch(err => console.error(err));
    },

    fetchConversationCounts: function() {
      if (osparc.store.Groups.getInstance().amIASupportUser()) {
        return Promise.all([
          this.fetchConversationCount("all"),
          this.fetchConversationCount("unread"),
          this.fetchConversationCount("active"),
          this.fetchConversationCount("archived"),
        ]).then(counts => {
          const conversationCounts = {
            all: counts[0],
            unread: counts[1],
            active: counts[2],
            archived: counts[3],
          };
          return conversationCounts;
        });
      } else {
        return Promise.all([
          this.fetchConversationCount("all"),
          this.fetchConversationCount("unread"),
        ]).then(counts => {
          const conversationCounts = {
            all: counts[0],
            unread: counts[1],
          };
          return conversationCounts;
        });
      }
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
          name: null,
          type,
          extraContext,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "postConversation", params)
        .then(conversationData => {
          const conversation = this.__addToCache(conversationData);
          this.fireDataEvent("conversationCreated", conversation);
          return conversationData;
        })
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
          this.__removeFromCache(conversationId);
          this.fireDataEvent("conversationDeleted", {
            conversationId,
          });
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
        name: name || null,
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

    archiveConversation: function(conversationId, archive) {
      const patchData = {
        "status": archive ? "ARCHIVED" : "ACTIVE",
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

    triggerChatbot: function(conversationId, messageId) {
      const params = {
        url: {
          conversationId,
          messageId,
        },
      };

      if (osparc.store.StaticInfo.isLocalEnv()) {
        return osparc.store.Faker.getInstance().triggerChatbot(conversationId, messageId);
      }
      return osparc.data.Resources.fetch("conversationsSupport", "triggerChatbot", params)
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

    __updateConversation: function(conversationData) {
      const conversationId = conversationData["conversationId"];
      const conversation = this.__conversationsCached[conversationId];
      if (conversation) {
        // Only the following properties can be updated:
        // name, extraContext, readByUser, readBySupport, isArchived
        if ("name" in conversationData) {
          conversation.setName(conversationData["name"]);
        }
        if (conversationData["extraContext"]) {
          conversation.setExtraContext(conversationData["extraContext"]);
        }
        if (typeof conversationData["isReadByUser"] === "boolean") {
          conversation.setReadByUser(conversationData["isReadByUser"]);
        }
        if (typeof conversationData["isReadBySupport"] === "boolean") {
          conversation.setReadBySupport(conversationData["isReadBySupport"]);
        }
        if (typeof conversationData["isArchived"] === "boolean") {
          conversation.setArchived(conversationData["isArchived"]);
        }
      }
    },

    __removeFromCache: function(conversationId) {
      if (conversationId in this.__conversationsCached) {
        delete this.__conversationsCached[conversationId];
      }
    },
  }
});
