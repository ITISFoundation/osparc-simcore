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
   * @param studyId {String} ID of the Study
   * */
  construct: function(conversationData, studyId) {
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
      studyId: studyId || null,
    });

    this.__messages = [];
    this.__listenToConversationMessageWS();

    if (conversationData.type === "SUPPORT") {
      this.__fetchFirstAndLastMessages();
    }
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
      apply: "__applyName",
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

    nameAlias: {
      check: "String",
      nullable: false,
      init: "",
      event: "changeNameAlias",
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

    studyId: {
      check: "String",
      nullable: true,
      init: null,
    },
  },

  events: {
    "messageAdded": "qx.event.type.Data",
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
  },

  members: {
    __fetchingFirstAndLastMessage: null,
    __nextRequestParams: null,
    __messages: null,

    __applyName: function(name) {
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

    __listenToConversationMessageWS: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      [
        this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED,
      ].forEach(eventName => {
        const eventHandler = message => {
          if (message) {
            const conversationId = message["conversationId"];
            if (conversationId === this.getConversationId()) {
              switch (eventName) {
                case this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED:
                  this.addMessage(message);
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED:
                  this.updateMessage(message);
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED:
                  this.deleteMessage(message);
                  break;
              }
            }
          }
        };
        socket.on(eventName, eventHandler, this);
      });
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
      if (this.getStudyId()) {
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
      const promise = this.getStudyId() ?
        osparc.data.Resources.fetch("conversationsStudies", "getMessagesPage", params, options) :
        osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params, options);
      return promise
        .then(resp => {
          const messages = resp["data"];
          messages.forEach(message => this.addMessage(message));
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

    patchExtraContext: function(extraContext) {
      osparc.store.ConversationsSupport.getInstance().patchExtraContext(this.getConversationId(), extraContext)
        .then(() => {
          this.setExtraContext(extraContext);
        });
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

    addMessage: function(messageData) {
      let message = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
      if (!message) {
        message = new osparc.data.model.Message(messageData);
        this.__messageToList(message);
      }
      return message;
    },

    __messageToList: function(message) {
      this.__messages.push(message);
      osparc.data.model.Message.sortMessagesByDate(this.__messages);
      this.setLastMessage(this.__messages[0]);
      this.fireDataEvent("messageAdded", message);
    },

    updateMessage: function(messageData) {
      if (messageData) {
        const found = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
        if (found) {
          found.setData(messageData);
          this.fireDataEvent("messageUpdated", found);
        }
      }
    },

    deleteMessage: function(messageData) {
      if (messageData) {
        const found = this.__messages.find(msg => msg.getMessageId() === messageData["messageId"]);
        if (found) {
          this.__messages.splice(this.__messages.indexOf(found), 1);
          this.fireDataEvent("messageDeleted", found);
        }
      }
    },

    getContextProjectId: function() {
      if (this.getExtraContext() && "projectId" in this.getExtraContext()) {
        return this.getExtraContext()["projectId"];
      }
      return null;
    },

    getFogbugzLink: function() {
      if (this.getExtraContext() && "fogbugz_case_url" in this.getExtraContext()) {
        return this.getExtraContext()["fogbugz_case_url"];
      }
      return null;
    },

    getAppointment: function() {
      if (this.getExtraContext() && "appointment" in this.getExtraContext()) {
        return this.getExtraContext()["appointment"];
      }
      return null;
    },

    setAppointment: function(appointment) {
      const extraContext = this.getExtraContext() || {};
      extraContext["appointment"] = appointment ? appointment.toISOString() : null;
      // OM: Supporters are not allowed to patch the conversation metadata yet
      const backendAllowsPatch = osparc.store.Groups.getInstance().amIASupportUser() ? false : true;
      if (backendAllowsPatch) {
        return osparc.store.ConversationsSupport.getInstance().patchExtraContext(this.getConversationId(), extraContext)
          .then(() => {
            this.setExtraContext(Object.assign({}, extraContext));
        });
      }
      return Promise.resolve(this.setExtraContext(Object.assign({}, extraContext)));
    },
  },
});
