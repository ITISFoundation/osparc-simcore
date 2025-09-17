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

    this.__messages = [];
    this.__listenToConversationMessageWS();

    if (conversationData.type === "SUPPORT") {
      this.__fetchLastMessage();
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

    lastMessage: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeLastMessage",
      apply: "__applyLastMessage",
    },
  },

  events: {
    "messageAdded": "qx.event.type.Data",
    "messageUpdated": "qx.event.type.Data",
    "messageDeleted": "qx.event.type.Data",
  },

  members: {
    __fetchLastMessagePromise: null,
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
        this.setNameAlias(lastMessage ? lastMessage.content : "");
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

    __fetchLastMessage: function() {
      if (this.__fetchLastMessagePromise) {
        return this.__fetchLastMessagePromise;
      }

      let promise = osparc.store.ConversationsSupport.getInstance().fetchLastMessage(this.getConversationId());
      promise
        .then(lastMessage => {
          this.addMessage(lastMessage);
          promise = null;
          return lastMessage;
        })
        .finally(() => {
          this.__fetchLastMessagePromise = null;
        });

      this.__fetchLastMessagePromise = promise;
      return promise;
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
      const nextRequestParams = this.__nextRequestParams;
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("conversationsSupport", "getMessagesPage", params, options)
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
        .then(() => {
          this.setName(newName);
        });
    },

    patchExtraContext: function(extraContext) {
      osparc.store.ConversationsSupport.getInstance().patchExtraContext(this.getConversationId(), extraContext)
        .then(() => {
          this.setExtraContext(extraContext);
        });
    },

    addMessage: function(message) {
      if (message) {
        const found = this.__messages.find(msg => msg["messageId"] === message["messageId"]);
        if (!found) {
          this.__messages.push(message);
          this.fireDataEvent("messageAdded", message);
        }
        // latest first
        this.__messages.sort((a, b) => new Date(b.created) - new Date(a.created));
        this.setLastMessage(this.__messages[0]);
      }
    },

    updateMessage: function(message) {
      if (message) {
        const found = this.__messages.find(msg => msg["messageId"] === message["messageId"]);
        if (found) {
          Object.assign(found, message);
          this.fireDataEvent("messageUpdated", found);
        }
      }
    },

    deleteMessage: function(message) {
      if (message) {
        const found = this.__messages.find(msg => msg["messageId"] === message["messageId"]);
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
