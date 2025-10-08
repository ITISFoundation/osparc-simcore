/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.ConversationsProject", {
  extend: qx.core.Object,
  type: "singleton",

  events: {
    "conversationRenamed": "qx.event.type.Data",
    "conversationDeleted": "qx.event.type.Data",
  },

  statics: {
    TYPES: {
      PROJECT_STATIC: "PROJECT_STATIC",
      PROJECT_ANNOTATION: "PROJECT_ANNOTATION",
    },
  },

  members: {
    getConversations: function(studyId) {
      const params = {
        url: {
          studyId,
          offset: 0,
          limit: 42,
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "getConversationsPage", params)
        .then(conversations => {
          if (conversations.length) {
            // Sort conversations by created date, oldest first (the new ones will be next to the plus button)
            conversations.sort((a, b) => new Date(a["created"]) - new Date(b["created"]));
          }
          return conversations;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    getConversation: function(studyId, conversationId) {
      const params = {
        url: {
          studyId,
          conversationId,
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "getConversation", params);
    },

    postConversation: function(studyId, name = "new 1", type = osparc.store.ConversationsProject.TYPES.PROJECT_STATIC) {
      const params = {
        url: {
          studyId,
        },
        data: {
          name,
          type,
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "postConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteConversation: function(studyId, conversationId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
      };
      return osparc.data.Resources.fetch("conversationsStudies", "deleteConversation", params)
        .then(() => {
          this.fireDataEvent("conversationDeleted", {
            studyId,
            conversationId,
          })
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    renameConversation: function(studyId, conversationId, name) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          name,
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "renameConversation", params)
        .then(() => {
          this.fireDataEvent("conversationRenamed", {
            studyId,
            conversationId,
            name,
          });
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    postMessage: function(studyId, conversationId, message) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          "content": message,
          "type": "MESSAGE",
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "postMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    editMessage: function(message, content, studyId) {
      const conversationId = message.getConversationId();
      const messageId = message.getMessageId();
      const params = {
        url: {
          studyId,
          conversationId,
          messageId,
        },
        data: {
          content,
        },
      };
      return osparc.data.Resources.fetch("conversationsStudies", "editMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteMessage: function(message, studyId) {
      const conversationId = message.getConversationId();
      const messageId = message.getMessageId();
      const params = {
        url: {
          studyId,
          conversationId,
          messageId,
        },
      };
      return osparc.data.Resources.fetch("conversationsStudies", "deleteMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    notifyUser: function(studyId, conversationId, userGroupId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          "content": userGroupId.toString(), // eventually the backend will accept integers
          "type": "NOTIFICATION",
        }
      };
      return osparc.data.Resources.fetch("conversationsStudies", "postMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },
  }
});
