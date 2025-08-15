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

    addConversation: function(name = "new 1", type = osparc.study.Conversations.TYPES.PROJECT_STATIC) {
      const params = {
        data: {
          name,
          type,
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
      return osparc.data.Resources.fetch("conversationsSupport", "renameConversation", params)
        .then(() => {
          this.fireDataEvent("conversationRenamed", {
            conversationId,
            name,
          });
        })
        .catch(err => osparc.FlashMessenger.logError(err));
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
