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


qx.Class.define("osparc.support.Conversation", {
  extend: qx.ui.core.Widget,

  /**
    * @param conversationId {String} Conversation Id
    */
  construct: function(conversationId) {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();

    if (conversationId) {
      this.setConversationId(conversationId);
    }
  },

  properties: {
    conversationId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeConversationId",
      apply: "__applyConversationId",
    },
  },

  members: {
    __messages: null,
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "messages-container-scroll":
          control = new qx.ui.container.Scroll();
          this._addAt(control, 0, {
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
          this._addAt(control, 1);
          break;
        case "support-suggestion":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            alignY: "middle"
          });
          this._addAt(control, 2);
          break;
        case "add-message":
          control = new osparc.conversation.AddMessage().set({
            padding: 10,
          });
          this.bind("conversationId", control, "conversationId");
          // make it more compact
          control.getChildControl("comment-field").getChildControl("tabs").getChildControl("bar").exclude();
          control.getChildControl("comment-field").getChildControl("subtitle").exclude();
          this._addAt(control, 3);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("messages-container");
      const addMessages = this.getChildControl("add-message");
      addMessages.addListener("messageAdded", e => {
        const data = e.getData();
        if (data["conversationId"]) {
          this.setConversationId(data["conversationId"]);
          this.addMessage(data);
        }
      });
    },

    __applyConversationId: function(conversationId) {
      this.__reloadMessages(true);

      const supportSuggestion = this.getChildControl("support-suggestion");
      supportSuggestion.exclude();
      if (conversationId === null && osparc.store.Store.getInstance().getCurrentStudy()) {
        supportSuggestion.show();
        const suggestedQuestion = new osparc.support.SuggestedQuestion();
        const answers = [
          { label: this.tr("No"), key: "no" },
          { label: this.tr("Yes"), key: "yes" },
        ];
        suggestedQuestion.isProjectRelated(answers);
        suggestedQuestion.addListener("questionAnswered", e => {
          const answer = e.getData();
          console.log(answer);
        });
        supportSuggestion.add(suggestedQuestion);
      }
    },

    __getNextRequest: function() {
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
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __reloadMessages: function(removeMessages = true) {
      const messagesContainer = this.getChildControl("messages-container");
      const loadMoreMessages = this.getChildControl("load-more-button");
      if (this.getConversationId() === null) {
        messagesContainer.hide();
        loadMoreMessages.hide();
        return;
      }

      messagesContainer.show();
      loadMoreMessages.show();
      loadMoreMessages.setFetching(true);

      if (removeMessages) {
        this.__messages = [];
        messagesContainer.removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const messages = resp["data"];
          messages.forEach(message => this.addMessage(message));
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null && loadMoreMessages) {
            loadMoreMessages.exclude();
          }
        })
        .finally(() => loadMoreMessages.setFetching(false));
    },

    addMessage: function(message) {
      // ignore it if it was already there
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex !== -1) {
        return;
      }

      // determine insertion index for latest‐first order
      const newTime = new Date(message["created"]);
      let insertAt = this.__messages.findIndex(m => new Date(m["created"]) > newTime);
      if (insertAt === -1) {
        insertAt = this.__messages.length;
      }

      // Insert the message in the messages array
      this.__messages.splice(insertAt, 0, message);

      // Add the UI element to the messages list
      let control = null;
      switch (message["type"]) {
        case "MESSAGE":
          control = new osparc.conversation.MessageUI(message);
          control.addListener("messageUpdated", e => this.updateMessage(e.getData()));
          control.addListener("messageDeleted", e => this.deleteMessage(e.getData()));
          break;
        case "NOTIFICATION":
          control = new osparc.conversation.NotificationUI(message);
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
    },

    deleteMessage: function(message) {
      // remove it from the messages array
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this.__messages.splice(messageIndex, 1);

      // Remove the UI element from the messages list
      const messagesContainer = this.getChildControl("messages-container");
      const children = messagesContainer.getChildren();
      const controlIndex = children.findIndex(
        ctrl => ("getMessage" in ctrl && ctrl.getMessage()["messageId"] === message["messageId"])
      );
      if (controlIndex > -1) {
        messagesContainer.remove(children[controlIndex]);
      }
    },

    updateMessage: function(message) {
      // Replace the message in the messages array
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this.__messages[messageIndex] = message;

      // Update the UI element from the messages list
      const messagesContainer = this.getChildControl("messages-container");
      messagesContainer.getChildren().forEach(control => {
        if ("getMessage" in control && control.getMessage()["messageId"] === message["messageId"]) {
          control.setMessage(message);
          return;
        }
      });
    },
  }
});
