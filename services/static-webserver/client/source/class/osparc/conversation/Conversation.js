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


qx.Class.define("osparc.conversation.Conversation", {
  extend: qx.ui.tabview.Page,

  /**
    * @param studyData {String} Study Data
    * @param conversationId {String} Conversation Id
    */
  construct: function(studyData, conversationId) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__messages = [];

    if (conversationId) {
      this.setConversationId(conversationId);
    }

    this._setLayout(new qx.ui.layout.VBox(5));

    this.set({
      padding: 10,
      showCloseButton: false,
    });

    this.getChildControl("button").set({
      font: "text-13",
    });
    this.__addConversationButtons();

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

  events: {
    "conversationDeleted": "qx.event.type.Event",
  },

  members: {
    __studyData: null,
    __messages: null,
    __nextRequestParams: null,
    __messagesTitle: null,
    __messagesList: null,
    __loadMoreMessages: null,

    __addConversationButtons: function() {
      const tabButton = this.getChildControl("button");

      const buttonsAesthetics = {
        focusable: false,
        keepActive: true,
        padding: 0,
        backgroundColor: "transparent",
      };
      const renameButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/pencil-alt/10").set({
        ...buttonsAesthetics,
        visibility: osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]) ? "visible" : "excluded",
      });
      renameButton.addListener("execute", () => {
        const titleEditor = new osparc.widget.Renamer(tabButton.getLabel());
        titleEditor.addListener("labelChanged", e => {
          titleEditor.close();
          const newLabel = e.getData()["newLabel"];
          if (this.getConversationId()) {
            osparc.store.Conversations.getInstance().renameConversation(this.__studyData["uuid"], this.getConversationId(), newLabel)
              .then(() => this.renameConversation(newLabel));
          } else {
            // create new conversation first
            osparc.store.Conversations.getInstance().addConversation(this.__studyData["uuid"], newLabel)
              .then(data => {
                this.setConversationId(data["conversationId"]);
                this.getChildControl("button").setLabel(newLabel);
              });
          }
        }, this);
        titleEditor.center();
        titleEditor.open();
      });
      // eslint-disable-next-line no-underscore-dangle
      tabButton._add(renameButton, {
        row: 0,
        column: 3
      });

      const closeButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
        ...buttonsAesthetics,
        paddingLeft: 4, // adds spacing between buttons
        visibility: osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]) ? "visible" : "excluded",
      });
      closeButton.addListener("execute", () => {
        if (this.__messagesList.getChildren().length === 0) {
          osparc.store.Conversations.getInstance().deleteConversation(this.__studyData["uuid"], this.getConversationId());
        } else {
          const msg = this.tr("Are you sure you want to delete the conversation?");
          const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
            caption: this.tr("Delete Conversation"),
            confirmText: this.tr("Delete"),
            confirmAction: "delete"
          });
          confirmationWin.open();
          confirmationWin.addListener("close", () => {
            if (confirmationWin.getConfirmed()) {
              osparc.store.Conversations.getInstance().deleteConversation(this.__studyData["uuid"], this.getConversationId());
            }
          }, this);
        }
      });
      // eslint-disable-next-line no-underscore-dangle
      tabButton._add(closeButton, {
        row: 0,
        column: 4
      });
      this.bind("conversationId", closeButton, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
    },

    renameConversation: function(newName) {
      this.getChildControl("button").setLabel(newName);
    },

    __buildLayout: function() {
      this.__messagesTitle = new qx.ui.basic.Label();
      this._add(this.__messagesTitle);

      this.__messagesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        alignY: "middle"
      });
      const scrollView = new qx.ui.container.Scroll();
      scrollView.add(this.__messagesList);
      this._add(scrollView, {
        flex: 1
      });

      this.__loadMoreMessages = new osparc.ui.form.FetchButton(this.tr("Load more messages..."));
      this.__loadMoreMessages.addListener("execute", () => this.__reloadMessages(false));
      this._add(this.__loadMoreMessages);

      const addMessages = new osparc.conversation.AddMessage(this.__studyData, this.getConversationId()).set({
        enabled: osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]),
        paddingLeft: 10,
      });
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
          studyId: this.__studyData["uuid"],
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
      return osparc.data.Resources.fetch("conversations", "getMessagesPage", params, options)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __reloadMessages: function(removeMessages = true) {
      if (this.getConversationId() === null) {
        this.__messagesTitle.setValue(this.tr("No messages yet"));
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
          if (this.__nextRequestParams === null) {
            this.__loadMoreMessages.exclude();
          }
        })
        .finally(() => this.__loadMoreMessages.setFetching(false));
    },

    __updateMessagesNumber: function() {
      const nMessages = this.__messages.filter(msg => msg["type"] === "MESSAGE").length;
      if (nMessages === 1) {
        this.__messagesTitle.setValue(this.tr("1 Message"));
      } else if (nMessages > 1) {
        this.__messagesTitle.setValue(nMessages + this.tr(" Messages"));
      }
    },

    addMessage: function(message) {
      // backend doesn't provide the projectId
      message["projectId"] = this.__studyData["uuid"];

      // ignore it if it was already there
      const messageIndex = this.__messages.findIndex(msg => msg["messageId"] === message["messageId"]);
      if (messageIndex !== -1) {
        return;
      }

      // determine insertion index for most‐recent‐first order
      const newTime = new Date(message["created"]);
      let insertAt = this.__messages.findIndex(m => new Date(m["created"]) < newTime);
      if (insertAt === -1) {
        insertAt = this.__messages.length;
      }

      // Insert the message in the messages array
      this.__messages.splice(insertAt, 0, message);

      // Add the UI element to the messages list
      let control = null;
      switch (message["type"]) {
        case "MESSAGE":
          control = new osparc.conversation.MessageUI(message, this.__studyData);
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
      // backend doesn't provide the projectId
      message["projectId"] = this.__studyData["uuid"];

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
