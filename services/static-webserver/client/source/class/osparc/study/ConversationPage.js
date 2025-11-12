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


qx.Class.define("osparc.study.ConversationPage", {
  extend: qx.ui.tabview.Page,

  /**
   * @param studyData {String} Study Data
    * @param conversationData {Object} Conversation Data
    */
  construct: function(studyData, conversationData) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__messages = [];

    this._setLayout(new qx.ui.layout.VBox(5));

    this.set({
      padding: 10,
      showCloseButton: false,
    });


    this.bind("conversation", this.getChildControl("button"), "label", {
      converter: conversation => conversation ? conversation.getName() : this.tr("new")
    });
    this.getChildControl("button").set({
      font: "text-13",
    });
    this.__addConversationButtons();

    this.__buildLayout();

    if (conversationData) {
      const conversation = new osparc.data.model.ConversationProject(conversationData, this.__studyData["uuid"]);
      this.setConversation(conversation);
    }

  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: true,
      event: "changeConversation",
    },
  },

  members: {
    __studyData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "n-messages":
          control = new qx.ui.basic.Label();
          this._add(control);
          break;
        case "conversation":
          control = new osparc.study.Conversation(this.__studyData);
          this.bind("conversation", control, "conversation");
          control.addListener("messagesChanged", () => this.__updateMessagesNumber());
          this._add(control, {
            flex: 1,
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("n-messages");
      this.getChildControl("conversation");
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
        const titleEditor = new osparc.widget.Renamer(tabButton.getLabel()).set({
          maxChars: osparc.data.model.Conversation.MAX_TITLE_LENGTH,
        });
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
                const conversation = new osparc.data.model.ConversationProject(data, this.__studyData["uuid"]);
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
      const messages = this.getChildControl("conversation").getMessages();
        if (messages.length === 0) {
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

    __updateMessagesNumber: function() {
      if (this.getConversation()) {
        const nMessagesLabel = this.getChildControl("n-messages");
        const messages = this.getConversation().getMessages();
        const nMessages = messages.filter(msg => msg.getType() === "MESSAGE").length;
        if (nMessages === 0) {
          nMessagesLabel.setValue(this.tr("No Messages yet"));
        } else if (nMessages === 1) {
          nMessagesLabel.setValue(this.tr("1 Message"));
        } else if (nMessages > 1) {
          nMessagesLabel.setValue(nMessages + this.tr(" Messages"));
        }
      }
    },
  }
});
