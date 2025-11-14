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


qx.Class.define("osparc.conversation.MessageList", {
  extend: qx.ui.core.Widget,

  /**
    * @param conversation {osparc.data.model.Conversation} Conversation
    */
  construct: function(conversation) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this._buildLayout();

    if (conversation) {
      this.setConversation(conversation);
    }
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: true,
      event: "changeConversation",
      apply: "_applyConversation",
    },
  },

  events: {
    "messagesChanged": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "spacer-top":
          control = new qx.ui.core.Spacer();
          this._addAt(control, 0, {
            flex: 100 // high number to keep even a one message list at the bottom
          });
          break;
        case "messages-container-scroll":
          control = new qx.ui.container.Scroll();
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "messages-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            alignY: "middle"
          });
          this.getChildControl("messages-container-scroll").add(control);
          break;
        case "load-more-button":
          control = new osparc.ui.form.FetchButton(this.tr("Load more messages..."));
          control.addListener("execute", () => this.__reloadMessages(false));
          this._addAt(control, 2);
          break;
        case "add-message":
          control = new osparc.conversation.AddMessage().set({
            padding: 5,
          });
          this.bind("conversation", control, "conversationId", {
            converter: conversation => conversation ? conversation.getConversationId() : null
          });
          this._addAt(control, 3);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("spacer-top");
      this.getChildControl("messages-container");
      this.getChildControl("add-message");
    },

    _applyConversation: function(conversation) {
      this.__reloadMessages(true);

      if (conversation) {
        conversation.addListener("messageAdded", e => {
          const data = e.getData();
          this._messageAdded(data);
        });
        conversation.addListener("messageDeleted", e => {
          const data = e.getData();
          this.__messageDeleted(data);
        });
      }
    },

    __reloadMessages: function(removeMessages = true) {
      if (removeMessages) {
        this.clearAllMessages();
      }

      const loadMoreMessages = this.getChildControl("load-more-button");
      if (this.getConversation() === null) {
        loadMoreMessages.hide();
        return;
      }

      this.getConversation().getMessages().forEach(message => this._messageAdded(message));

      loadMoreMessages.show();
      loadMoreMessages.setFetching(true);
      this.getConversation().getNextMessages()
        .then(resp => {
          if (resp["_links"]["next"] === null && loadMoreMessages) {
            loadMoreMessages.exclude();
          }
        })
        .finally(() => loadMoreMessages.setFetching(false));
    },

    _createMessageUI: function(message) {
      return new osparc.conversation.MessageUI(message);
    },

    getMessages: function() {
      return this.getConversation().getMessages();
    },

    clearAllMessages: function() {
      this.getChildControl("messages-container").removeAll();
      this.fireEvent("messagesChanged");
    },

    __getMessageUI: function(messageId) {
      const messagesContainer = this.getChildControl("messages-container");
      return messagesContainer.getChildren().find(
        ctrl => ("getMessage" in ctrl && ctrl.getMessage().getMessageId() === messageId)
      );
    },

    _messageAdded: function(message) {
      // ignore it if it was already there
      const existingMessageUI = this.__getMessageUI(message.getMessageId());
      if (existingMessageUI) {
        return;
      }

      // Add the UI element to the messages list
      let control = null;
      switch (message.getType()) {
        case "MESSAGE":
          control = this._createMessageUI(message);
          control.addListener("messageDeleted", e => this.__messageDeleted(e.getData()));
          break;
        case "NOTIFICATION":
          control = new osparc.conversation.NotificationUI(message);
          break;
      }
      if (control && this.getConversation()) {
        // insert into the UI at the same position
        const insertAt = this.getConversation().getMessageIndex(message.getMessageId());
        const messagesContainer = this.getChildControl("messages-container");
        messagesContainer.addAt(control, insertAt);
      }

      // scroll to bottom
      // add timeout to ensure the scroll happens after the UI is updated
      setTimeout(() => {
        const messagesScroll = this.getChildControl("messages-container-scroll");
        messagesScroll.scrollToY(messagesScroll.getChildControl("pane").getScrollMaxY());
      }, 50);

      this.fireEvent("messagesChanged");
    },

    __messageDeleted: function(message) {
      // Remove the UI element from the messages list
      const existingMessageUI = this.__getMessageUI(message.getMessageId());
      if (existingMessageUI) {
        const messagesContainer = this.getChildControl("messages-container");
        messagesContainer.remove(existingMessageUI);
      }

      this.fireEvent("messagesChanged");
    },
  }
});
