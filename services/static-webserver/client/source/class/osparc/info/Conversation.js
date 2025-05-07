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


qx.Class.define("osparc.info.Conversation", {
  extend: qx.ui.tabview.Page,

  /**
    * @param studyData {String} Study Data
    * @param conversationId {String} Conversation Id
    */
  construct: function(studyData, conversationId) {
    this.base(arguments);

    this.__studyData = studyData;

    if (conversationId) {
      this.setConversationId(conversationId);
    }

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 10,
      showCloseButton: false,
    });

    this.getChildControl("button").set({
      font: "text-13",
    });
    this.__addConversationButtons();

    this.__buildLayout();

    this.fetchMessages();
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
      });
      renameButton.addListener("execute", () => {
        const titleEditor = new osparc.widget.Renamer(tabButton.getLabel());
        titleEditor.addListener("labelChanged", e => {
          titleEditor.close();
          const newLabel = e.getData()["newLabel"];
          if (this.getConversationId()) {
            osparc.study.Conversations.renameConversation(this.__studyData["uuid"], this.getConversationId(), newLabel)
              .then(() => {
                this.getChildControl("button").setLabel(newLabel);
              });
          } else {
            // create new conversation first
            osparc.study.Conversations.addConversation(this.__studyData["uuid"], newLabel)
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

      const trashButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
        ...buttonsAesthetics,
        paddingLeft: 4, // adds spacing between buttons
      });
      trashButton.addListener("execute", () => {
        const deleteConversation = () => {
          osparc.study.Conversations.deleteConversation(this.__studyData["uuid"], this.getConversationId())
            .then(() => this.fireEvent("conversationDeleted"));
        }
        if (this.__messagesList.getChildren().length === 0) {
          deleteConversation();
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
              deleteConversation();
            }
          }, this);
        }
      });
      // eslint-disable-next-line no-underscore-dangle
      tabButton._add(trashButton, {
        row: 0,
        column: 4
      });
      this.bind("conversationId", trashButton, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
    },

    __buildLayout: function() {
      this.__messagesTitle = new qx.ui.basic.Label();
      this._add(this.__messagesTitle);

      this.__messagesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        alignY: "middle"
      });
      this._add(this.__messagesList, {
        flex: 1
      });

      this.__loadMoreMessages = new osparc.ui.form.FetchButton(this.tr("Load more messages..."));
      this.__loadMoreMessages.addListener("execute", () => this.fetchMessages(false));
      this._add(this.__loadMoreMessages);

      if (osparc.data.model.Study.canIWrite(this.__studyData["accessRights"])) {
        const addMessages = new osparc.info.CommentAdd(this.__studyData["uuid"], this.getConversationId());
        addMessages.setPaddingLeft(10);
        addMessages.addListener("commentAdded", e => {
          const data = e.getData();
          if (data["conversationId"]) {
            this.setConversationId(data["conversationId"]);
          }
          this.fetchMessages();
        });
        this._add(addMessages);
      }
    },

    fetchMessages: function(removeMessages = true) {
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
        this.__messagesList.removeAll();
      }

      this.__getNextRequest()
        .then(resp => {
          const messages = resp["data"];
          this.__addMessages(messages);
          this.__nextRequestParams = resp["_links"]["next"];
          if (this.__nextRequestParams === null) {
            this.__loadMoreMessages.exclude();
          }
        })
        .finally(() => this.__loadMoreMessages.setFetching(false));
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
      return osparc.data.Resources.fetch("conversations", "getMessagesPage", params, options);
    },

    __addMessages: function(messages) {
      if (messages.length === 1) {
        this.__messagesTitle.setValue(this.tr("1 Message"));
      } else if (messages.length > 1) {
        this.__messagesTitle.setValue(messages.length + this.tr(" Messages"));
      }

      messages.forEach(message => {
        const messageUi = new osparc.info.CommentUI(message);
        this.__messagesList.add(messageUi);
      });
    },
  }
});
