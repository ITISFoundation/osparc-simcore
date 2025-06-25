/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.study.Conversations", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {String} Study Data
    */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__conversations = [];

    this.fetchConversations(studyData);

    this.__listenToConversationWS();
  },

  statics: {
    popUpInWindow: function(studyData) {
      const conversations = new osparc.study.Conversations(studyData);
      const title = qx.locale.Manager.tr("Conversations");
      const viewWidth = 600;
      const viewHeight = 700;
      const win = osparc.ui.window.Window.popUpInWindow(conversations, title, viewWidth, viewHeight);
      return win;
    },

    addConversation: function(studyId, name = "new 1") {
      const params = {
        url: {
          studyId,
        },
        data: {
          name,
          "type": "PROJECT_STATIC",
        }
      };
      return osparc.data.Resources.fetch("conversations", "addConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteConversation: function(studyId, conversationId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
      };
      return osparc.data.Resources.fetch("conversations", "deleteConversation", params)
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
      return osparc.data.Resources.fetch("conversations", "renameConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    addMessage: function(studyId, conversationId, message) {
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
      return osparc.data.Resources.fetch("conversations", "addMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    editMessage: function(studyId, conversationId, messageId, message) {
      const params = {
        url: {
          studyId,
          conversationId,
          messageId,
        },
        data: {
          "content": message,
        },
      };
      return osparc.data.Resources.fetch("conversations", "editMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteMessage: function(message) {
      const params = {
        url: {
          studyId: message["projectId"],
          conversationId: message["conversationId"],
          messageId: message["messageId"],
        },
      };
      return osparc.data.Resources.fetch("conversations", "deleteMessage", params)
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
      return osparc.data.Resources.fetch("conversations", "addMessage", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },
  },

  members: {
    __conversations: null,
    __wsHandlers: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.tabview.TabView();
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
        "conversation:created",
        "conversation:updated",
        "conversation:deleted",
      ].forEach(eventName => {
        const eventHandler = conversation => {
          if (conversation) {
            switch (eventName) {
              case "conversation:created":
                conversation.addMessage(conversation);
                break;
              case "conversation:updated":
                conversation.updateMessage(conversation);
                break;
              case "conversation:deleted":
                conversation.deleteMessage(conversation);
                break;
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });

      [
        "conversation:message:created",
        "conversation:message:updated",
        "conversation:message:deleted",
      ].forEach(eventName => {
        const eventHandler = message => {
          if (message) {
            const conversationId = message["conversationId"];
            const conversation = this.__getConversation(conversationId);
            if (conversation) {
              switch (eventName) {
                case "conversation:message:created":
                  conversation.addMessage(message);
                  break;
                case "conversation:message:updated":
                  conversation.updateMessage(message);
                  break;
                case "conversation:message:deleted":
                  conversation.deleteMessage(message);
                  break;
              }
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });
    },

    __getConversation: function(conversationId) {
      return this.__conversations.find(conversation => conversation.getConversationId() === conversationId);
    },

    fetchConversations: function(studyData) {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      const params = {
        url: {
          studyId: studyData["uuid"],
          offset: 0,
          limit: 42,
        }
      };
      osparc.data.Resources.fetch("conversations", "getConversationsPage", params)
        .then(conversations => this.__addConversations(conversations, studyData))
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },

    __addConversations: function(conversations, studyData) {
      const conversationPages = [];
      const conversationsLayout = this.getChildControl("conversations-layout");

      const newConversationButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/plus/12",
        toolTipText: this.tr("Add new conversation"),
        allowGrowX: false,
        backgroundColor: "transparent",
      });

      const reloadConversations = () => {
        conversationPages.forEach(conversationPage => conversationPage.fireDataEvent("close", conversationPage));
        conversationsLayout.getChildControl("bar").remove(newConversationButton);
        this.fetchConversations(studyData);
      };

      this.__conversations = [];
      if (conversations.length === 0) {
        const noConversationTab = new osparc.conversation.Conversation(studyData);
        conversationPages.push(noConversationTab);
        noConversationTab.setLabel(this.tr("new"));
        noConversationTab.addListener("conversationDeleted", () => reloadConversations());
        conversationsLayout.add(noConversationTab);
      } else {
        conversations.forEach(conversationData => {
          const conversationId = conversationData["conversationId"];
          const conversation = new osparc.conversation.Conversation(studyData, conversationId);
          this.__conversations.push(conversation);
          conversationPages.push(conversation);
          conversation.setLabel(conversationData["name"]);
          conversation.addListener("conversationDeleted", () => reloadConversations());
          conversationsLayout.add(conversation);
        });
      }

      newConversationButton.addListener("execute", () => {
        osparc.study.Conversations.addConversation(studyData["uuid"], "new " + (conversations.length + 1))
          .then(() => {
            reloadConversations();
          });
      });

      conversationsLayout.getChildControl("bar").add(newConversationButton);
    },
  },

  destruct: function() {
    const socket = osparc.wrapper.WebSocket.getInstance();
    if (this.__wsHandlers) {
      this.__wsHandlers.forEach(({ eventName }) => {
        socket.removeSlot(eventName);
      });
      this.__wsHandlers = null;
    }
  },
});
