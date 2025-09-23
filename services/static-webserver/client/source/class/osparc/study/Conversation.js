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


qx.Class.define("osparc.study.Conversation", {
  extend: qx.ui.tabview.Page,

  /**
    * @param conversationData {Object} Conversation Data
    * @param studyData {String} Study Data
    */
  construct: function(conversationData, studyData) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__messages = [];

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

    if (conversationData) {
      const conversation = new osparc.data.model.Conversation(conversationData, this.__studyData);
      this.setConversation(conversation);
      this.setLabel(conversationData["name"]);
    } else {
      this.setLabel(this.tr("new"));
    }
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: false,
      event: "changeConversation",
      apply: "__applyConversation",
    },
  },

  members: {
    __studyData: null,
    __messages: null,
    __nextRequestParams: null,
    __messagesTitle: null,
    __messageScroll: null,
    __messagesList: null,
    __loadMoreMessages: null,

    __applyConversation: function(conversation) {
      this.__reloadMessages(true);

      conversation.addListener("messageAdded", e => {
        const message = e.getData();
        this.addMessage(message);
      }, this);
      conversation.addListener("messageUpdated", e => {
        const message = e.getData();
        this.updateMessage(message);
      }, this);
      conversation.addListener("messageDeleted", e => {
        const message = e.getData();
        this.deleteMessage(message);
      }, this);
    },

    getConversationId: function() {
      if (this.getConversation()) {
        return this.getConversation().getConversationId();
      }
      return null;
    },

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
            osparc.store.ConversationsProject.getInstance().renameConversation(this.__studyData["uuid"], this.getConversationId(), newLabel)
              .then(() => this.renameConversation(newLabel));
          } else {
            // create new conversation first
            osparc.store.ConversationsProject.getInstance().postConversation(this.__studyData["uuid"], newLabel)
              .then(data => {
                const conversation = new osparc.data.model.Conversation(data, this.__studyData);
                this.setConversation(conversation);
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
          osparc.store.ConversationsProject.getInstance().deleteConversation(this.__studyData["uuid"], this.getConversationId());
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
              osparc.store.ConversationsProject.getInstance().deleteConversation(this.__studyData["uuid"], this.getConversationId());
            }
          }, this);
        }
      });
      // eslint-disable-next-line no-underscore-dangle
      tabButton._add(closeButton, {
        row: 0,
        column: 4
      });
      this.bind("conversation", closeButton, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
    },

    renameConversation: function(newName) {
      this.getChildControl("button").setLabel(newName);
    },

    __buildLayout: function() {
      this.__messagesTitle = new qx.ui.basic.Label();
      this._add(this.__messagesTitle);

      // add spacer to keep the messages list at the bottom
      this._add(new qx.ui.core.Spacer(), {
        flex: 100 // high number to keep even a one message list at the bottom
      });

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

      const addMessage = new osparc.conversation.AddMessage().set({
        studyData: this.__studyData,
        enabled: osparc.data.model.Study.canIWrite(this.__studyData["accessRights"]),
        paddingLeft: 10,
      });
      this.bind("conversation", addMessage, "conversationId", {
        converter: conversation => conversation ? conversation.getConversationId() : null
      });
      addMessage.addListener("addMessage", e => {
        const content = e.getData();
        const conversation = this.getConversation();
        if (conversation) {
          this.__postMessage(content);
        } else {
          // create new conversation first
          osparc.store.ConversationsProject.getInstance().postConversation(this.__studyData["uuid"])
            .then(data => {
              const newConversation = new osparc.data.model.Conversation(data, this.__studyData);
              this.setConversation(newConversation);
              this.__postMessage(content);
            });
        }
      });
      addMessage.addListener("notifyUser", e => {
        const userGid = e.getData();
        const conversation = this.getConversation();
        if (conversation) {
          this.__postNotify(userGid);
        } else {
          // create new conversation first
          osparc.store.ConversationsProject.getInstance().postConversation(this.__studyData["uuid"])
            .then(data => {
              const newConversation = new osparc.data.model.Conversation(data, this.__studyData);
              this.setConversation(newConversation);
              this.__postNotify(userGid);
            });
        }
      });
      this._add(addMessage);
    },

    __postMessage: function(content) {
      const conversationId = this.getConversation().getConversationId();
      osparc.store.ConversationsProject.getInstance().postMessage(this.__studyData["uuid"], conversationId, content);
    },

    __postNotify: function(userGid) {
      const conversationId = this.getConversation().getConversationId();
      osparc.store.ConversationsProject.getInstance().notifyUser(this.__studyData["uuid"], conversationId, userGid)
        .then(data => {
          this.fireDataEvent("messageAdded", data);
          const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators();
          if (userGid in potentialCollaborators) {
            if ("getUserId" in potentialCollaborators[userGid]) {
              const uid = potentialCollaborators[userGid].getUserId();
              osparc.notification.Notifications.pushConversationNotification(uid, this.__studyData["uuid"]);
            }
            const msg = "getLabel" in potentialCollaborators[userGid] ? potentialCollaborators[userGid].getLabel() + this.tr(" was notified") : this.tr("Notification sent");
            osparc.FlashMessenger.logAs(msg, "INFO");
          }
        });
    },

    __reloadMessages: function(removeMessages = true) {
      if (this.getConversationId() === null) {
        // temporary conversation page
        this.__messagesTitle.setValue(this.tr("No Messages yet"));
        this.__messagesList.hide();
        this.__loadMoreMessages.hide();
        return;
      }

      if (removeMessages) {
        this.__messages = [];
        this.__messagesList.removeAll();
      }
      this.__messagesList.show();

      this.__loadMoreMessages.show();
      this.__loadMoreMessages.setFetching(true);
      this.getConversation().getNextMessages()
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

    __updateMessagesNumber: function() {
      if (!this.__messagesTitle) {
        return;
      }
      const nMessages = this.__messages.filter(msg => msg["type"] === "MESSAGE").length;
      if (nMessages === 0) {
        this.__messagesTitle.setValue(this.tr("No Messages yet"));
      } else if (nMessages === 1) {
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
          control = new osparc.conversation.MessageUI(message, this.__studyData);
          control.getChildControl("message-content").set({
            measurerMaxWidth: 400,
          });
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
          // Force a new reference
          control.setMessage(Object.assign({}, message));
          return;
        }
      });
    },
  }
});
