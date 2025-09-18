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
    * @param conversation {osparc.data.model.Conversation} Conversation
    */
  construct: function(conversation) {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();

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
      apply: "__applyConversation",
    },

    studyId: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeStudyId",
      apply: "__applyStudyId",
    },
  },

  statics: {
    SYSTEM_MESSAGE_TYPE: {
      ASK_A_QUESTION: "askAQuestion",
      BOOK_A_CALL: "bookACall",
      BOOK_A_CALL_3RD: "bookACall3rd",
      ESCALATE_TO_SUPPORT: "escalateToSupport",
      REPORT_OEC: "reportOEC",
      FOLLOW_UP: "followUp",
    },
  },

  members: {
    __messages: null,

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
          control.addListener("execute", () => this.__reloadMessages());
          this._addAt(control, 2);
          break;
        case "support-suggestion":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
            alignY: "middle"
          });
          this._addAt(control, 3);
          break;
        case "add-message":
          control = new osparc.conversation.AddMessage().set({
            padding: 5,
          });
          this.bind("conversation", control, "conversationId", {
            converter: conversation => conversation ? conversation.getConversationId() : null
          });
          this._addAt(control, 4);
          break;
        case "share-project-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
            backgroundColor: "strong-main",
            decorator: "rounded",
          });
          this._addAt(control, 5);
          break;
        case "share-project-checkbox":
          control = new qx.ui.form.CheckBox().set({
            value: false,
            label: this.tr("Share Project with Support"),
            textColor: "white",
            padding: 3,
          });
          this.getChildControl("share-project-layout").add(new qx.ui.core.Spacer(), { flex: 1 });
          this.getChildControl("share-project-layout").add(control);
          this.getChildControl("share-project-layout").add(new qx.ui.core.Spacer(), { flex: 1 });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("spacer-top");
      this.getChildControl("messages-container");
      const addMessages = this.getChildControl("add-message");
      addMessages.addListener("addMessage", e => {
        const content = e.getData();
        const conversation = this.getConversation();
        if (conversation) {
          this.__postMessage(content);
        } else {
          // create new conversation first
          const extraContext = {};
          const currentStudy = osparc.store.Store.getInstance().getCurrentStudy()
          if (currentStudy) {
            extraContext["projectId"] = currentStudy.getUuid();
          }
          osparc.store.ConversationsSupport.getInstance().postConversation(extraContext)
            .then(data => {
              let prePostMessagePromise = new Promise((resolve) => resolve());
              let isBookACall = false;
              // make these checks first, setConversation will reload messages
              if (
                this.__messages.length === 1 &&
                this.__messages[0]["systemMessageType"] &&
                this.__messages[0]["systemMessageType"] === osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL
              ) {
                isBookACall = true;
              }
              const newConversation = new osparc.data.model.Conversation(data);
              this.setConversation(newConversation);
              if (isBookACall) {
                // add a first message
                prePostMessagePromise = this.__postMessage("Book a Call");
                // rename the conversation
                newConversation.renameConversation("Book a Call");
              }
              prePostMessagePromise
                .then(() => {
                  // add the actual message
                  return this.__postMessage(content);
                })
                .then(() => {
                  setTimeout(() => this.addSystemMessage("followUp"), 1000);
                });
            });
        }
      });
    },

    __postMessage: function(content) {
      const conversationId = this.getConversation().getConversationId();
      return osparc.store.ConversationsSupport.getInstance().postMessage(conversationId, content);
    },

    __applyConversation: function(conversation) {
      this.clearAllMessages();
      this.__reloadMessages();

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

      this.__populateShareProjectCheckbox();
    },

    __populateShareProjectCheckbox: function() {
      const conversation = this.getConversation();

      const shareProjectCB = this.getChildControl("share-project-checkbox");
      const shareProjectLayout = this.getChildControl("share-project-layout");
      const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
      let showCB = false;
      let enabledCB = false;
      if (conversation === null && currentStudy) {
        // initiating conversation
        showCB = true;
        enabledCB = true;
      } else if (conversation) {
        // it was already set
        showCB = conversation.getContextProjectId();
        enabledCB = conversation.amIOwner();
      }
      shareProjectLayout.set({
        visibility: showCB ? "visible" : "excluded",
        enabled: enabledCB,
      });

      if (conversation && conversation.getContextProjectId()) {
        const projectId = conversation.getContextProjectId();
        osparc.store.Study.getInstance().getOne(projectId)
          .then(studyData => {
            let isAlreadyShared = false;
            const accessRights = studyData["accessRights"];
            const supportGroupId = osparc.store.Groups.getInstance().getSupportGroup().getGroupId();
            if (supportGroupId && supportGroupId in accessRights) {
              isAlreadyShared = true;
            } else {
              isAlreadyShared = false;
            }
            shareProjectCB.setValue(isAlreadyShared);
            shareProjectCB.removeListener("changeValue", this.__shareProjectWithSupport, this);
            if (showCB) {
              shareProjectCB.addListener("changeValue", this.__shareProjectWithSupport, this);
            }
          });
      }
    },

    __shareProjectWithSupport: function(e) {
      const share = e.getData();
      const supportGroupId = osparc.store.Groups.getInstance().getSupportGroup().getGroupId();
      const projectId = this.getConversation().getContextProjectId();
      osparc.store.Study.getInstance().getOne(projectId)
        .then(studyData => {
          if (share) {
            const newCollaborators = {
              [supportGroupId]: osparc.data.Roles.STUDY["write"].accessRights
            };
            osparc.store.Study.getInstance().addCollaborators(studyData, newCollaborators)
          } else {
            osparc.store.Study.getInstance().removeCollaborator(studyData, supportGroupId);
          }
        });
    },

    __reloadMessages: function() {
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

    addSystemMessage: function(type) {
      type = type || osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION;

      const now = new Date();
      const systemMessage = {
        "conversationId": null,
        "created": now.toISOString(),
        "messageId": `system-${now.getTime()}`,
        "modified": now.toISOString(),
        "type": "MESSAGE",
        "userGroupId": "system",
      };
      let msg = null;
      const greet = "Hi " + osparc.auth.Data.getInstance().getUserName() + ",\n";
      switch (type) {
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION:
          msg = greet + "Have a question or feedback?\nWe are happy to assist!";
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL:
          msg = greet + "Let us know what your availability is and we will get back to you shortly to schedule a meeting.";
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ESCALATE_TO_SUPPORT:
          msg = greet + "Our support team will take it from here — please confirm or edit your question below to get started.";
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.FOLLOW_UP:
          msg = "A support ticket has been created.\nOur team will review your request and contact you soon.";
          break;
      }
      if (msg) {
        systemMessage["content"] = msg;
        systemMessage["systemMessageType"] = type;
        this.addMessage(systemMessage);
      }
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

    clearAllMessages: function() {
      this.__messages = [];
      this.getChildControl("messages-container").removeAll();
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
      const messageUI = messagesContainer.getChildren().find(control => {
        return "getMessage" in control && control.getMessage()["messageId"] === message["messageId"];
      });
      if (messageUI) {
        // Force a new reference
        messageUI.setMessage(Object.assign({}, message));
      }
    },
  }
});
