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

    this._messages = [];

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
    _messages: null,

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
          this.addMessage(data);
        });
        conversation.addListener("messageUpdated", e => {
          const data = e.getData();
          this.updateMessage(data);
        });
        conversation.addListener("messageDeleted", e => {
          const data = e.getData();
          this.deleteMessage(data);
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

      loadMoreMessages.show();
      loadMoreMessages.setFetching(true);
      this.getConversation().getNextMessages()
        .then(resp => {
          const messages = resp["data"];
          messages.forEach(message => this.addMessage(message));
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
      return this._messages;
    },

    clearAllMessages: function() {
      this._messages = [];
      this.getChildControl("messages-container").removeAll();

      this.fireEvent("messagesChanged");
    },

    addMessage: function(messageData) {
      // ignore it if it was already there
      const messageIndex = this._messages.findIndex(msg => msg.getMessageId() === messageData["messageId"]);
      if (messageIndex !== -1) {
        return;
      }

      // determine insertion index for latest‐first order
      const newTime = new Date(messageData["created"]);
      let insertAt = this._messages.findIndex(m => new Date(m["created"]) > newTime);
      if (insertAt === -1) {
        insertAt = this._messages.length;
      }

      // Insert the message in the messages array
      const message = new osparc.data.model.Message(messageData);
      this._messages.splice(insertAt, 0, message);

      // Add the UI element to the messages list
      let control = null;
      switch (message.getType()) {
        case "MESSAGE":
          control = this._createMessageUI(messageData);
          control.addListener("messageUpdated", e => this.updateMessage(e.getData()));
          control.addListener("messageDeleted", e => this.deleteMessage(e.getData()));
          break;
        case "NOTIFICATION":
          control = new osparc.conversation.NotificationUI(messageData);
          break;
      }
      if (control) {
        // insert into the UI at the same position
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

    deleteMessage: function(messageData) {
      // remove it from the messages array
      const messageIndex = this._messages.findIndex(msg => msg.getMessageId() === messageData["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this._messages.splice(messageIndex, 1);

      // Remove the UI element from the messages list
      const messagesContainer = this.getChildControl("messages-container");
      const children = messagesContainer.getChildren();
      const controlIndex = children.findIndex(
        ctrl => ("getMessage" in ctrl && ctrl.getMessage()["messageId"] === messageData["messageId"])
      );
      if (controlIndex > -1) {
        messagesContainer.remove(children[controlIndex]);
      }

      this.fireEvent("messagesChanged");
    },

    updateMessage: function(messageData) {
      // Replace the message in the messages array
      const messageIndex = this._messages.findIndex(msg => msg.getMessageId() === messageData["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this._messages[messageIndex] = messageData;

      // Update the UI element from the messages list
      const messagesContainer = this.getChildControl("messages-container");
      const messageUI = messagesContainer.getChildren().find(control => {
        return "getMessage" in control && control.getMessage()["messageId"] === messageData["messageId"];
      });
      if (messageUI) {
        // Force a new reference
        messageUI.setMessage(Object.assign({}, messageData));
      }
    },
  }
});
