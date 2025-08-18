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


qx.Class.define("osparc.support.Conversation", {
  extend: qx.ui.core.Widget,

  /**
    * @param conversationId {String} Conversation Id
    */
  construct: function(conversationId) {
    this.base(arguments);

    this.__messages = [];

    if (conversationId) {
      this.setConversationId(conversationId);
    }

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();

    this.__reloadMessages();
  },

  properties: {
    conversationId: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeConversationId"
    },
  },

  members: {
    __messages: null,
    __nextRequestParams: null,
    __messageScroll: null,
    __messagesList: null,
    __loadMoreMessages: null,

    __buildLayout: function() {
      this.__messagesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        alignY: "middle"
      });
      const scrollView = this.__messageScroll = new qx.ui.container.Scroll();
      scrollView.add(this.__messagesList);
      this._add(scrollView, {
        flex: 1
      });

      this.__loadMoreMessages = new osparc.ui.form.FetchButton(this.tr("Load more messages..."));
      this.__loadMoreMessages.addListener("execute", () => this.__reloadMessages(false));
      this._add(this.__loadMoreMessages);

      const addMessages = new osparc.conversation.AddMessage().set({
        padding: 5,
      });
      this.bind("conversationId", addMessages, "conversationId");
      addMessages.addListener("messageAdded", e => {
        const data = e.getData();
        if (data["conversationId"]) {
          this.setConversationId(data["conversationId"]);
          this.addMessage(data);
        }
      });
      this._add(addMessages);
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
      return osparc.data.Resources.fetch("conversationsStudies", "getMessagesPage", params, options)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __reloadMessages: function(removeMessages = true) {
      if (this.getConversationId() === null) {
        this.__messagesList.hide();
        this.__loadMoreMessages.hide();
        return;
      }

      this.__messagesList.show();
      this.__loadMoreMessages.show();
      this.__loadMoreMessages.setFetching(true);

      if (removeMessages) {
        this.__messages = [];
        this.__messagesList.removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const messages = resp["data"];
          messages.forEach(message => this.addMessage(message));
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null && this.__loadMoreMessages) {
            this.__loadMoreMessages.exclude();
          }
        })
        .finally(() => this.__loadMoreMessages.setFetching(false));
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
        this.__messagesList.addAt(control, insertAt);
      }

      // scroll to bottom
      // add timeout to ensure the scroll happens after the UI is updated
      setTimeout(() => {
        this.__messageScroll.scrollToY(this.__messageScroll.getChildControl("pane").getScrollMaxY());
      }, 50);

      this.__updateMessagesNumber();
    },

    deleteMessage: function(message) {
      // remove it from the messages array
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this.__messages.splice(messageIndex, 1);

      // Remove the UI element from the messages list
      const children = this.__messagesList.getChildren();
      const controlIndex = children.findIndex(
        ctrl => ("getMessage" in ctrl && ctrl.getMessage()["messageId"] === message["messageId"])
      );
      if (controlIndex > -1) {
        this.__messagesList.remove(children[controlIndex]);
      }

      this.__updateMessagesNumber();
    },

    updateMessage: function(message) {
      // Replace the message in the messages array
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex === -1) {
        return;
      }
      this.__messages[messageIndex] = message;

      // Update the UI element from the messages list
      this.__messagesList.getChildren().forEach(control => {
        if ("getMessage" in control && control.getMessage()["messageId"] === message["messageId"]) {
          control.setMessage(message);
          return;
        }
      });
    },
  }
});
