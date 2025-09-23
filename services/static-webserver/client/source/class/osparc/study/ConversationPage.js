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
      const conversation = new osparc.data.model.Conversation(conversationData, this.__studyData);
      this.setConversation(conversation);
    }

  },

  properties: {
    conversation: {
      check: "osparc.data.model.Conversation",
      init: null,
      nullable: false,
      event: "changeConversation",
    },
  },

  members: {
    __studyData: null,

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
        // if (this.__messagesList.getChildren().length === 0) {
        if (this._messages.length === 0) {
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

      const conversation = new osparc.study.Conversation(this.__studyData);
      this.bind("conversation", conversation, "conversation");
      this._add(conversation, {
        flex: 1,
      });
    },

    __updateMessagesNumber: function() {
      if (!this.__messagesTitle) {
        return;
      }
      const nMessages = this._messages.filter(msg => msg["type"] === "MESSAGE").length;
      if (nMessages === 0) {
        this.__messagesTitle.setValue(this.tr("No Messages yet"));
      } else if (nMessages === 1) {
        this.__messagesTitle.setValue(this.tr("1 Message"));
      } else if (nMessages > 1) {
        this.__messagesTitle.setValue(nMessages + this.tr(" Messages"));
      }
    },
  }
});
