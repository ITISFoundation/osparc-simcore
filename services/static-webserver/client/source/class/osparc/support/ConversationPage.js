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


qx.Class.define("osparc.support.ConversationPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-button");

    const conversation = this.getChildControl("conversation-content");
    this.bind("conversation", conversation, "conversation");
    conversation.bind("conversation", this, "conversation");
  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: true,
      event: "changeConversation",
      apply: "__applyConversation",
    },
  },

  events: {
    "backToConversations": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversation-header-layout": {
          const headerLayout = new qx.ui.layout.HBox(5).set({
            alignY: "middle",
          })
          control = new qx.ui.container.Composite(headerLayout).set({
            padding: 5,
          });
          this._add(control);
          break;
        }
        case "back-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Return to Conversations"),
            icon: "@FontAwesome5Solid/arrow-left/16",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => {
            if (this.getConversation()) {
              this.getConversation().setReadBy(true);
            }
            this.setConversation(null);
            this.fireEvent("backToConversations");
          });
          this.getChildControl("conversation-header-layout").addAt(control, 0);
          break;
        case "conversation-header-center-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("conversation-header-layout").addAt(control, 1, {
            flex: 1,
          });
          break;
        case "conversation-title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
            });
          this.getChildControl("conversation-header-center-layout").addAt(control, 0);
          break;
        case "conversation-extra-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
          this.getChildControl("conversation-header-center-layout").addAt(control, 1);
          break;
        case "options-button":{
          const buttonSize = 22;
          control = new qx.ui.menu.Button().set({
            appearance: "form-button-outlined",
            width: buttonSize,
            height: buttonSize,
            padding: [0, 8, 0, 8],
            allowGrowX: false,
            allowGrowY: false,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          this.getChildControl("conversation-header-layout").addAt(control, 2);
          break;
        }
        case "options-menu":
          control = new qx.ui.menu.Menu().set({
            appearance: "menu-wider",
            position: "bottom-left",
          });
          this.getChildControl("options-button").setMenu(control);
          break;
        case "rename-button": {
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/i-cursor/12",
            label: this.tr("Rename"),
          });
          control.addListener("execute", () => this.__renameConversation());
          this.getChildControl("options-menu").addAt(control, 0);
          break;
        }
        case "open-project-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/external-link-alt/12",
            label: this.tr("Project details"),
          });
          control.addListener("execute", () => this.__openProjectDetails());
          this.getChildControl("options-menu").addAt(control, 1);
          break;
        case "copy-ticket-id-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/copy/12",
            label: this.tr("Copy Ticket ID"),
          });
          control.addListener("execute", () => this.__copyTicketId());
          this.getChildControl("options-menu").addAt(control, 2);
          break;
        case "delete-button":
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/trash-alt/12",
            label: this.tr("Delete"),
          });
          control.addListener("execute", () => this.__deleteConversation(), this);
          this.getChildControl("options-menu").addAt(control, 3);
          break;
        case "main-stack":
          control = new qx.ui.container.Stack();
          this._add(control, {
            flex: 1
          });
          break;
        case "conversation-container":
          control = new qx.ui.container.Scroll();
          this.getChildControl("main-stack").add(control);
          break;
        case "conversation-content":
          control = new osparc.support.Conversation();
          this.getChildControl("conversation-container").add(control);
          break;
        case "book-a-call-topic-selector":
          control = new osparc.support.BookACallTopicSelector();
          this.getChildControl("main-stack").add(control);
          break;
        case "book-a-call-iframe":
          control = new osparc.wrapper.BookACallIframe();
          this.getChildControl("main-stack").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    proposeConversation: function(type, prefillText) {
      type = type || osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION;
      this.setConversation(null);

      const title = this.getChildControl("conversation-title");
      const conversationContent = this.getChildControl("conversation-content");
      conversationContent.clearAllMessages();
      const conversationContainer = this.getChildControl("conversation-container");
      this.getChildControl("main-stack").setSelection([conversationContainer]);
      switch (type) {
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION:
          title.setValue(this.tr("Ask a Question"));
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL:
          title.setValue(this.tr("Book a Call"));
          const bookACallTopicSelector = this.getChildControl("book-a-call-topic-selector");
          bookACallTopicSelector.getChildControl("next-button").setLabel(this.tr("Next"));
          bookACallTopicSelector.addListener("callTopicSelected", e => {
            const data = e.getData();
            conversationContent.addBookACallInfo(data);
            this.getChildControl("main-stack").setSelection([conversationContainer]);
          });
          this.getChildControl("main-stack").setSelection([bookACallTopicSelector]);
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL_3RD: {
          title.setValue(this.tr("Book a Call 3rd"));
          const bookACallTopicSelector = this.getChildControl("book-a-call-topic-selector");
          bookACallTopicSelector.getChildControl("next-button").setLabel(this.tr("Select date & time"));
          bookACallTopicSelector.addListener("callTopicSelected", e => {
            const data = e.getData();
            conversationContent.addBookACallInfo(data);
            this.getChildControl("main-stack").setSelection([conversationContainer]);
          });
          this.getChildControl("main-stack").setSelection([bookACallTopicSelector]);
          break;
        }
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ESCALATE_TO_SUPPORT:
          title.setValue(this.tr("Ask a Question"));
          break;
        case osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.REPORT_OEC:
          title.setValue(this.tr("Report an Error"));
          break;
      }
      conversationContent.addSystemMessage(type);

      if (prefillText) {
        this.getChildControl("conversation-content").getChildControl("add-message").getChildControl("comment-field").setText(prefillText);
      }
    },

    __applyConversation: function(conversation) {
      const extraContextLayout = this.getChildControl("conversation-extra-layout");
      extraContextLayout.removeAll();

      if (conversation) {
        const amISupporter = osparc.store.Groups.getInstance().amIASupportUser();

        const title = this.getChildControl("conversation-title");
        conversation.bind("nameAlias", title, "value");

        const createExtraContextLabel = text => {
          return new qx.ui.basic.Label(text).set({
            font: "text-12",
            textColor: "text-disabled",
            allowGrowX: true,
            selectable: true,
          });
        };
        const updateExtraContext = () => {
          extraContextLayout.removeAll();
          const extraContext = conversation.getExtraContext();
          if (extraContext && Object.keys(extraContext).length) {
            const ticketIdLabel = createExtraContextLabel(`Ticket ID: ${osparc.utils.Utils.uuidToShort(conversation.getConversationId())}`);
            extraContextLayout.add(ticketIdLabel);
            const contextProjectId = conversation.getContextProjectId();
            if (contextProjectId) {
              const projectIdLabel = createExtraContextLabel(`Project ID: ${osparc.utils.Utils.uuidToShort(contextProjectId)}`);
              extraContextLayout.add(projectIdLabel);
            }
            if (amISupporter) {
              const fogbugzLink = conversation.getFogbugzLink();
              if (fogbugzLink) {
                const text = "Fogbugz Case: " + fogbugzLink.split("/").pop();
                const fogbugzLabel = new osparc.ui.basic.LinkLabel(text, fogbugzLink).set({
                  font: "link-label-12",
                  textColor: "text-disabled",
                  allowGrowX: true,
                });
                extraContextLayout.add(fogbugzLabel);
              }
            }
          }
        };
        updateExtraContext();
        conversation.addListener("changeExtraContext", () => updateExtraContext(), this);

        const amIOwner = conversation.amIOwner();
        this.getChildControl("rename-button").set({
          enabled: amIOwner,
        });

        const openProjectButton = this.getChildControl("open-project-button");
        openProjectButton.exclude();
        if (conversation && conversation.getContextProjectId()) {
          openProjectButton.setVisibility("visible");
          osparc.store.Study.getInstance().getOne(conversation.getContextProjectId())
            .then(() => openProjectButton.setEnabled(true))
            .catch(() => openProjectButton.setEnabled(false));
        } else {
          openProjectButton.setVisibility("excluded");
        }

        this.getChildControl("copy-ticket-id-button");

        this.getChildControl("delete-button").set({
          enabled: amIOwner,
        });
      }

      this.getChildControl("options-button").setVisibility(conversation ? "visible" : "excluded");
    },

    __openProjectDetails: function() {
      const projectId = this.getConversation().getContextProjectId();
      if (projectId) {
        osparc.store.Study.getInstance().getOne(projectId)
          .then(studyData => {
            if (studyData) {
              const studyDataCopy = osparc.data.model.Study.deepCloneStudyObject(studyData);
              studyDataCopy["resourceType"] = "study";
              osparc.dashboard.ResourceDetails.popUpInWindow(studyDataCopy);
            }
          })
          .catch(err => console.warn(err));
      }
    },

    __copyTicketId: function() {
      if (this.getConversation()) {
        const conversationId = this.getConversation().getConversationId();
        osparc.utils.Utils.copyTextToClipboard(conversationId);
      }
    },

    __renameConversation: function() {
      let oldName = this.getConversation().getName();
      if (oldName === "null") {
        oldName = "";
      }
      const renamer = new osparc.widget.Renamer(oldName).set({
        maxChars: osparc.data.model.Conversation.MAX_TITLE_LENGTH,
      });
      renamer.addListener("labelChanged", e => {
        renamer.close();
        const newLabel = e.getData()["newLabel"];
        this.getConversation().renameConversation(newLabel);
      }, this);
      renamer.center();
      renamer.open();
    },

    __deleteConversation: function() {
      const conversation = this.getConversation();
      const win = new osparc.ui.window.Confirmation(this.tr("Delete conversation?")).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete",
      });
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          osparc.store.ConversationsSupport.getInstance().deleteConversation(conversation)
            .then(() => {
              this.setConversation(null);
              this.fireEvent("backToConversations");
            })
            .catch(err => osparc.FlashMessenger.logError(err));
        }
      });
    },

    __getAddMessageField: function() {
      return this.getChildControl("conversation-content") &&
        this.getChildControl("conversation-content").getChildControl("add-message");
    },

    postMessage: function(message) {
      const addMessage = this.__getAddMessageField();
      if (addMessage && addMessage.getChildControl("comment-field")) {
        addMessage.getChildControl("comment-field").setText(message);
        return addMessage.addComment();
      }
      return Promise.reject();
    },
  }
});
