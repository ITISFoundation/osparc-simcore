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
  extend: osparc.conversation.MessageList,

  /**
    * @param conversation {osparc.data.model.Conversation} Conversation
    */
  construct: function(conversation) {
    this.base(arguments, conversation);
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
    TRIGGER_CHATBOT_DELAY: 2000,
  },

  properties: {
    chatbotTriggerState: {
      check: ["idle", "waiting", "triggered"],
      init: "idle",
      nullable: false,
      event: "changeChatbotTriggerState",
    },
  },

  members: {
    __bookACallInfo: null,
    __triggerChatbotTimer: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thinking-response":
          control = new qx.ui.basic.Label(this.tr("thinking")).set({
            font: "text-13-italic",
            marginLeft: 50,
          });
          this.bind("chatbotTriggerState", control, "value", {
            converter: val => {
              switch (val) {
                case "waiting":
                  return this.tr("thinking");
                case "triggered":
                  return this.tr("thinking...");
                case "idle":
                  return "";
              }
            }
          });
          this.bind("chatbotTriggerState", control, "visibility", {
            converter: val => val === "idle" ? "excluded" : "visible"
          });
          this._addAt(control, osparc.conversation.MessageList.POS.THINKING_RESPONSE);
          break;
        case "share-project-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
            backgroundColor: "strong-main",
            decorator: "rounded",
          });
          this._addAt(control, osparc.conversation.MessageList.POS.SHARE_PROJECT_LAYOUT);
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
          control.addListener("tap", () => this.__shareProjectWithSupport(control.getValue()), this);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.base(arguments);

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
          // clone first, it will be reset when setting the conversation
          const bookACallInfo = this.__bookACallInfo ? Object.assign({}, this.__bookACallInfo) : null;
          const type = bookACallInfo ? osparc.store.ConversationsSupport.TYPES.SUPPORT_CALL : osparc.store.ConversationsSupport.TYPES.SUPPORT;
          osparc.store.ConversationsSupport.getInstance().postConversation(extraContext, type)
            .then(data => {
              const newConversation = new osparc.data.model.ConversationSupport(data);
              this.setConversation(newConversation);
              let prePostMessagePromise = new Promise((resolve) => resolve());
              if (bookACallInfo) {
                // add a first message
                let msg = "Book a Call";
                if (bookACallInfo) {
                  msg += `\n- Topic: ${bookACallInfo["topic"]}`;
                  if ("extraInfo" in bookACallInfo) {
                    msg += `\n- Extra Info: ${bookACallInfo["extraInfo"]}`;
                  }
                }
                prePostMessagePromise = this.__postMessage(msg);
                // rename the conversation
                newConversation.renameConversation("Book a Call");
                // share project if needed
                if (bookACallInfo["share-project"] && currentStudy) {
                  this.__shareProjectWithSupport(true);
                }
              }
              prePostMessagePromise
                .then(() => {
                  // add the actual message
                  return this.__postMessage(content);
                })
                .then(() => {
                  if (
                    !osparc.store.Groups.getInstance().isChatbotEnabled() ||
                    type === osparc.store.ConversationsSupport.TYPES.SUPPORT_CALL
                  ) {
                    // only add follow up message if there is no chatbot support
                    setTimeout(() => this.addSystemMessage(this.self().SYSTEM_MESSAGE_TYPE.FOLLOW_UP), 1000);
                  }
                });
            });
        }
      });

      addMessages.addListener("changeTyping", e => {
        const isTyping = e.getData();
        if (isTyping) {
          // if the user is typing, clear any previous chatbot trigger timer
          this.__clearTriggerChatbotTimer();
        } else {
          // if the user stopped typing, start the chatbot trigger timer if needed
          this.__startTriggerChatbotTimer();
        }
      }, this);

      this.getChildControl("thinking-response");
    },

    // overridden
    clearAllMessages: function() {
      this.base(arguments);

      this.__bookACallInfo = null;
    },

    _applyConversation: function(conversation) {
      this.base(arguments, conversation);

      this.__bookACallInfo = null;
      this.__evaluateShareProject();
    },

    // overridden
    _messageAdded: function(message) {
      this.base(arguments, message);

      // keep conversation read
      const conversation = this.getConversation();
      if (conversation) {
        conversation.setReadBy(true);
      }

      // hide thinking response if the message is from the chatbot
      if (
        osparc.store.Groups.getInstance().isChatbotEnabled() &&
        osparc.store.Groups.getInstance().getChatbot().getGroupId() === message.getUserGroupId()
      ) {
        this.setChatbotTriggerState("idle");
        this.__clearTriggerChatbotTimer();
      }
    },

    __postMessage: function(content) {
      const conversationId = this.getConversation().getConversationId();
      return osparc.store.ConversationsSupport.getInstance().postMessage(conversationId, content)
        .then(messageData => {
          this.__startTriggerChatbotTimer();
          return messageData;
        });
    },

    __startTriggerChatbotTimer: function() {
      // trigger chatbot only if:
      // - chatbot is enabled
      // - current user is not a support user
      // - conversation is of type SUPPORT
      // - conversation's last message is mine
      if (
        !osparc.store.Groups.getInstance().isChatbotEnabled() ||
        osparc.store.Groups.getInstance().amIASupportUser() ||
        !this.getConversation() ||
        this.getConversation().getType() !== osparc.store.ConversationsSupport.TYPES.SUPPORT ||
        this.getConversation().getLastMessage() && this.getConversation().getLastMessage().getUserGroupId() !== osparc.store.Groups.getInstance().getMyGroupId()
      ) {
        return;
      }

      // clear any previous timer
      this.__clearTriggerChatbotTimer();

      // show thinking response
      this.setChatbotTriggerState("waiting");
      // wait a bit before triggering the chatbot response
      // if the user starts typing again, the timer will be cleared
      const conversationId = this.getConversation().getConversationId();
      const messageId = this.getConversation().getLastMessage().getMessageId();
      this.__triggerChatbotTimer = setTimeout(() => {
        this.__triggerChatbotTimer = null;
        osparc.store.ConversationsSupport.getInstance().triggerChatbot(conversationId, messageId)
          .then(() => this.setChatbotTriggerState("triggered"))
          .catch(() => this.setChatbotTriggerState("idle"));
      }, this.self().TRIGGER_CHATBOT_DELAY);
    },

    __clearTriggerChatbotTimer: function() {
      // if the chatbot was already triggered, it can't be cleared
      if (this.getChatbotTriggerState() === "waiting") {
        this.setChatbotTriggerState("idle");
      }

      if (this.__triggerChatbotTimer) {
        clearTimeout(this.__triggerChatbotTimer);
        this.__triggerChatbotTimer = null;
      }
    },

    __evaluateShareProject: function() {
      const shareProjectLayout = this.getChildControl("share-project-layout");
      let showLayout = false;
      let enabledLayout = false;
      const conversation = this.getConversation();
      if (conversation) {
        showLayout = Boolean(conversation.getContextProjectId());
        enabledLayout = conversation.amIOwner();
      }
      shareProjectLayout.set({
        visibility: showLayout ? "visible" : "excluded",
        enabled: enabledLayout,
      });

      if (showLayout) {
        this.__populateShareProjectCB();
        const currentStudy = osparc.store.Store.getInstance().getCurrentStudy();
        if (currentStudy) {
          currentStudy.addListener("changeAccessRights", () => this.__populateShareProjectCB(), this);
        }
      }
    },

    __populateShareProjectCB: function() {
      const conversation = this.getConversation();
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
            const shareProjectCB = this.getChildControl("share-project-checkbox");
            shareProjectCB.setValue(isAlreadyShared);
          });
      }
    },

    __shareProjectWithSupport: function(share) {
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

    addSystemMessage: function(type) {
      type = type || osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION;

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
        const now = new Date();
        const systemMessageData = {
          "conversationId": null,
          "content": msg,
          "created": now.toISOString(),
          "messageId": `system-${now.getTime()}`,
          "modified": now.toISOString(),
          "type": "MESSAGE",
          "userGroupId": osparc.data.model.Message.SYSTEM_MESSAGE_ID,
        };
        const systemMessage = new osparc.data.model.Message(systemMessageData);
        const messageUI = new osparc.conversation.MessageUI(systemMessage);
        this.getChildControl("messages-container").add(messageUI);
      }
    },

    addBookACallInfo: function(bookACallInfo) {
      this.__bookACallInfo = bookACallInfo;
    },
  }
});
