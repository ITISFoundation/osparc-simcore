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
    this.__fetchLastMessage();
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
          this.setNameAlias(newName);
        });
    },

    addMessage: function(message) {
      if (message) {
        const found = this.__messages.find(msg => msg["messageId"] === message["messageId"]);
        if (!found) {
          this.__messages.push(message);
        }
        // latest first
        this.__messages.sort((a, b) => new Date(b.created) - new Date(a.created));
        this.setLastMessage(this.__messages[0]);
      }
    },

    getContextProjectId: function() {
      if (this.getExtraContext() && "projectId" in this.getExtraContext()) {
        return this.getExtraContext()["projectId"];
      }
      return null;
    }
  },
});
