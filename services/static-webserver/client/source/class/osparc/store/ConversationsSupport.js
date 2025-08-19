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

  events: {
    "conversationRenamed": "qx.event.type.Data",
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
        .then(conversations => {
          if (conversations.length) {
            // Sort conversations by created date, oldest first (the new ones will be next to the plus button)
            conversations.sort((a, b) => new Date(a["created"]) - new Date(b["created"]));
          }
          return conversations;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    getConversation: function(conversationId) {
      const params = {
        url: {
          conversationId,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getConversation", params);
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
        .then(data => {
          // OM PATCH the extra content
          // extraContext["conversationLink"] = `${url}#/conversation/${data["conversationId"]}`;
          return data;
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
      return osparc.data.Resources.fetch("conversationsSupport", "renameConversation", params)
        .then(() => {
          this.fireDataEvent("conversationRenamed", {
            conversationId,
            name,
          });
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    getLastMessage: function(conversationId) {
      const params = {
        url: {
          conversationId,
          offset: 0,
          limit: 1,
        }
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params);
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
  }
});
