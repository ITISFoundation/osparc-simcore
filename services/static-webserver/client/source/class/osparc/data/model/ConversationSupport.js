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
 * Class that stores Support Conversation data.
 */

qx.Class.define("osparc.data.model.ConversationSupport", {
  extend: osparc.data.model.Conversation,

  /**
   * @param conversationData {Object} Object containing the serialized Conversation Data
   * */
  construct: function(conversationData) {
    this.base(arguments, conversationData);

    this.set({
      projectId: conversationData.projectUuid || null,
      extraContext: conversationData.extraContext || null,
      fogbugzCaseId: conversationData["fogbugz_case_id"] || null,
      readByUser: Boolean(conversationData.isReadByUser),
      readBySupport: Boolean(conversationData.isReadBySupport),
    });

    this.__fetchFirstAndLastMessages();
  },

  properties: {
    nameAlias: {
      check: "String",
      nullable: false,
      init: "",
      event: "changeNameAlias",
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

    fogbugzCaseId: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeFogbugzCaseId",
    },

    firstMessage: {
      check: "osparc.data.model.Message",
      nullable: true,
      init: null,
      event: "changeFirstMessage",
    },

    lastMessage: {
      check: "osparc.data.model.Message",
      nullable: true,
      init: null,
      event: "changeLastMessage",
      apply: "__applyLastMessage",
    },

    readByUser: {
      check: "Boolean",
      nullable: false,
      init: null,
      event: "changeReadByUser",
    },

    readBySupport: {
      check: "Boolean",
      nullable: false,
      init: null,
      event: "changeReadBySupport",
    },
  },

  members: {
    __fetchingFirstAndLastMessage: null,

    _applyName: function(name) {
      if (name && name !== "null") {
        this.setNameAlias(name);
      }
    },

    __applyLastMessage: function(lastMessage) {
      const name = this.getName();
      if (!name || name === "null") {
        this.setNameAlias(lastMessage ? lastMessage.getContent() : "");
      }
    },

    __fetchFirstAndLastMessages: function() {
      if (this.__fetchingFirstAndLastMessage) {
        return this.__fetchingFirstAndLastMessage;
      }

      this.__fetchingFirstAndLastMessage = true;
      osparc.store.ConversationsSupport.getInstance().fetchLastMessage(this.getConversationId())
        .then(resp => {
          const messages = resp["data"];
          if (messages.length) {
            const lastMessage = new osparc.data.model.Message(messages[0]);
            this.setLastMessage(lastMessage);
          }
          // fetch first message only if there is more than one message
          if (resp["_meta"]["total"] === 1) {
            const firstMessage = new osparc.data.model.Message(messages[0]);
            this.setFirstMessage(firstMessage);
          } else if (resp["_meta"]["total"] > 1) {
            osparc.store.ConversationsSupport.getInstance().fetchFirstMessage(this.getConversationId(), resp["_meta"])
              .then(firstMessages => {
                if (firstMessages.length) {
                  const firstMessage = new osparc.data.model.Message(firstMessages[0]);
                  this.setFirstMessage(firstMessage);
                }
              });
          }
          return null;
        })
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.__fetchingFirstAndLastMessage = null);
    },

    patchExtraContext: function(extraContext) {
      osparc.store.ConversationsSupport.getInstance().patchExtraContext(this.getConversationId(), extraContext)
        .then(() => {
          this.setExtraContext(extraContext);
        });
    },

    setReadBy: function(isRead) {
      osparc.store.Groups.getInstance().amIASupportUser() ? this.setReadBySupport(isRead) : this.setReadByUser(isRead);
    },

    getReadBy: function() {
      return osparc.store.Groups.getInstance().amIASupportUser() ? this.getReadBySupport() : this.getReadByUser();
    },

    markAsRead: function() {
      osparc.store.ConversationsSupport.getInstance().markAsRead(this.getConversationId())
        .then(() => this.setReadBy(true));
    },

    // overriden
    _addMessage: function(messageData, markAsUnread = true) {
      const message = this.base(arguments, messageData);
      this.__evalFirstAndLastMessage();

      // mark conversation as unread if the message is from the other party
      if (markAsUnread && !osparc.data.model.Message.isMyMessage(message)) {
        this.setReadBy(false);
      }
      return message;
    },

    // overriden
    _updateMessage: function(messageData) {
      this.base(arguments, messageData);
      this.__evalFirstAndLastMessage();
    },

    // overriden
    _deleteMessage: function(messageData) {
      this.base(arguments, messageData);
      this.__evalFirstAndLastMessage();
    },

    __evalFirstAndLastMessage: function() {
      if (this.__messages && this.__messages.length) {
        // sort messages by date just in case
        osparc.data.model.Message.sortMessagesByDate(this.__messages);
        // newest first
        this.setFirstMessage(this.__messages[0]);
        this.setLastMessage(this.__messages[this.__messages.length - 1]);
      }
    },

    getContextProjectId: function() {
      if (this.getExtraContext() && "projectId" in this.getExtraContext()) {
        return this.getExtraContext()["projectId"];
      }
      return null;
    },

    getFogbugzLink: function() {
      if (this.getFogbugzCaseId()) {
        return this.getFogbugzCaseId();
      }
      if (this.getExtraContext() && "fogbugz_case_url" in this.getExtraContext()) {
        return this.getExtraContext()["fogbugz_case_url"];
      }
      return null;
    },
  },
});
