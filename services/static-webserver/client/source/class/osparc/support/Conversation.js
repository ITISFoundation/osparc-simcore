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
          control.addListener("execute", () => this.__reloadMessages(false));
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
          // make it more compact
          control.getChildControl("comment-field").getChildControl("tabs").getChildControl("bar").exclude();
          control.getChildControl("comment-field").getChildControl("subtitle").exclude();
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
      addMessages.addListener("messageAdded", e => {
        const data = e.getData();
        if (data["conversationId"] && this.getConversation() === null) {
          osparc.store.ConversationsSupport.getInstance().getConversation(data["conversationId"])
            .then(conversation => {
              this.setConversation(conversation);
            });
        } else {
          this.getConversation().addMessage(data);
          this.addMessage(data);
        }
      });
    },

    __applyConversation: function(conversation) {
      this.__reloadMessages(true);

      if (conversation) {
        conversation.addListener("messageAdded", e => {
          const data = e.getData();
          this.addMessage(data);
        });
        conversation.addListener("messageUpdated", e => {
          const data = e.getData();
          console.log("Message updated:", data);
        });
        conversation.addListener("messageDeleted", e => {
          const data = e.getData();
          console.log("Message deleted:", data);
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
            const supportGroupId = osparc.store.Products.getInstance().getSupportGroupId();
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
      const supportGroupId = osparc.store.Products.getInstance().getSupportGroupId();
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

    __reloadMessages: function(removeMessages = true) {
      const messagesContainer = this.getChildControl("messages-container");
      const loadMoreMessages = this.getChildControl("load-more-button");
      if (this.getConversation() === null) {
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
