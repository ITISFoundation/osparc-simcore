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


qx.Class.define("osparc.support.Conversations", {
  extend: qx.ui.core.Widget,

  construct: function(openConversationId = null) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__conversationListItems = [];
    this.__openConversationId = openConversationId;

    this.__fetchConversations();
    this.__listenToConversationWS();
  },

  statics: {
    TYPES: {
      SUPPORT: "SUPPORT",
    },

    CHANNELS: {
      CONVERSATION_CREATED: "conversation:created",
      CONVERSATION_UPDATED: "conversation:updated",
      CONVERSATION_DELETED: "conversation:deleted",
      CONVERSATION_MESSAGE_CREATED: "conversation:message:created",
      CONVERSATION_MESSAGE_UPDATED: "conversation:message:updated",
      CONVERSATION_MESSAGE_DELETED: "conversation:message:deleted",
    },
  },

  members: {
    __conversationListItems: null,
    __openConversationId: null,
    __wsHandlers: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox());
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __listenToConversationWS: function() {
      this.__wsHandlers = [];

      const socket = osparc.wrapper.WebSocket.getInstance();

      [
        this.self().CHANNELS.CONVERSATION_CREATED,
        this.self().CHANNELS.CONVERSATION_UPDATED,
        this.self().CHANNELS.CONVERSATION_DELETED,
      ].forEach(eventName => {
        const eventHandler = conversation => {
          if (conversation) {
            switch (eventName) {
              case this.self().CHANNELS.CONVERSATION_CREATED:
                if (!conversation["projectId"]) {
                  this.__addConversation(conversation);
                }
                break;
              case this.self().CHANNELS.CONVERSATION_UPDATED:
                this.__updateConversationName(conversation);
                break;
              case this.self().CHANNELS.CONVERSATION_DELETED:
                this.__removeConversationItem(conversation["conversationId"]);
                break;
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });

      [
        this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED,
        this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED,
      ].forEach(eventName => {
        const eventHandler = message => {
          if (message) {
            const conversationId = message["conversationId"];
            const conversationPage = this.__getConversationItem(conversationId);
            if (conversationPage) {
              switch (eventName) {
                case this.self().CHANNELS.CONVERSATION_MESSAGE_CREATED:
                  conversationPage.addMessage(message);
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_UPDATED:
                  conversationPage.updateMessage(message);
                  break;
                case this.self().CHANNELS.CONVERSATION_MESSAGE_DELETED:
                  conversationPage.deleteMessage(message);
                  break;
              }
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });
    },

    __getConversationItem: function(conversationId) {
      return this.__conversationListItems.find(conversation => conversation.getConversationId() === conversationId);
    },

    __fetchConversations: function() {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      osparc.store.ConversationsSupport.getInstance().getConversations()
        .then(conversations => {
          if (conversations.length) {
            conversations.forEach(conversation => this.__addConversation(conversation));
            if (this.__openConversationId) {
              const conversationsLayout = this.getChildControl("conversations-layout");
              const conversation = conversationsLayout.getSelectables().find(c => c.getConversationId() === this.__openConversationId);
              if (conversation) {
                conversationsLayout.setSelection([conversation]);
              }
              this.__openConversationId = null; // reset it so it does not open again
            }
          }
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },

    __addConversation: function(conversationData) {
      // ignore it if it was already there
      const conversationId = conversationData["conversationId"];
      const conversationItemFound = this.__getConversationItem(conversationId);
      if (conversationItemFound) {
        return null;
      }

      const conversationListItem = new osparc.support.ConversationListItem();
      conversationListItem.setConversationId(conversationData["conversationId"]);

      const conversationsLayout = this.getChildControl("conversations-layout");
      conversationsLayout.add(conversationListItem);

      this.__conversationListItems.push(conversationListItem);

      return conversationListItem;
    },

    __removeConversationItem: function(conversationId, changeSelection = false) {
      const conversationItem = this.__getConversationItem(conversationId);
      if (conversationItem) {
        const conversationsLayout = this.getChildControl("conversations-layout");
        if (conversationsLayout.indexOf(conversationItem) > -1) {
          conversationsLayout.remove(conversationItem);
        }
        this.__conversationListItems = this.__conversationListItems.filter(c => c !== conversationItem);
        const conversationPages = conversationsLayout.getSelectables();
        if (conversationPages.length) {
          if (changeSelection) {
            // change selection to the first conversation
            conversationsLayout.setSelection([conversationPages[0]]);
          }
        }
      }
    },

    // it can only be renamed, not updated
    __updateConversationName: function(conversationData) {
      const conversationId = conversationData["conversationId"];
      const conversationPage = this.__getConversationItem(conversationId);
      if (conversationPage) {
        conversationPage.renameConversation(conversationData["name"]);
      }
    },

    // overridden
    destroy: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (this.__wsHandlers) {
        this.__wsHandlers.forEach(({ eventName }) => {
          socket.removeSlot(eventName);
        });
        this.__wsHandlers = null;
      }

      this.base(arguments);
    },
  },
});
