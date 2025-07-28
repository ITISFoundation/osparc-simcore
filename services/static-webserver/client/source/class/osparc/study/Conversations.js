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


qx.Class.define("osparc.study.Conversations", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} Study Data
    */
  construct: function(studyData, openConversationId = null) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__conversationsPages = [];
    this.__openConversationId = openConversationId;

    this.set({
      studyData,
    });

    this.__listenToConversationWS();
  },

  properties: {
    studyData: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "__applyStudyData",
    },
  },

  statics: {
    TYPES: {
      PROJECT_STATIC: "PROJECT_STATIC",
      PROJECT_ANNOTATION: "PROJECT_ANNOTATION",
    },

    popUpInWindow: function(studyData, openConversationId = null) {
      const conversations = new osparc.study.Conversations(studyData, openConversationId);
      const title = qx.locale.Manager.tr("Conversations");
      const viewWidth = 600;
      const viewHeight = 700;
      const win = osparc.ui.window.Window.popUpInWindow(conversations, title, viewWidth, viewHeight);
      win.addListener("close", () => {
        conversations.destroy();
      }, this);
      return win;
    },
  },

  members: {
    __openConversationId: null,
    __conversations: null,
    __newConversationButton: null,
    __wsHandlers: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.tabview.TabView();
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __listenToConversationWS: function() {
      this.__wsHandlers = [];

      const socket = osparc.wrapper.WebSocket.getInstance();

      [
        "conversation:created",
        "conversation:updated",
        "conversation:deleted",
      ].forEach(eventName => {
        const eventHandler = conversation => {
          if (conversation) {
            switch (eventName) {
              case "conversation:created":
                this.__addConversationPage(conversation);
                break;
              case "conversation:updated":
                this.__updateConversationName(conversation);
                break;
              case "conversation:deleted":
                this.__removeConversationPage(conversation["conversationId"]);
                break;
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });

      [
        "conversation:message:created",
        "conversation:message:updated",
        "conversation:message:deleted",
      ].forEach(eventName => {
        const eventHandler = message => {
          if (message) {
            const conversationId = message["conversationId"];
            const conversationPage = this.__getConversationPage(conversationId);
            if (conversationPage) {
              switch (eventName) {
                case "conversation:message:created":
                  conversationPage.addMessage(message);
                  break;
                case "conversation:message:updated":
                  conversationPage.updateMessage(message);
                  break;
                case "conversation:message:deleted":
                  conversationPage.deleteMessage(message);
                  break;
              }
            }
          }
        };
        socket.on(eventName, eventHandler, this);
        this.__wsHandlers.push({ eventName, handler: eventHandler });
      });
    },

    __getConversationPage: function(conversationId) {
      return this.__conversationsPages.find(conversation => conversation.getConversationId() === conversationId);
    },

    __applyStudyData: function(studyData) {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      osparc.store.Conversations.getInstance().getConversations(studyData["uuid"])
        .then(conversations => {
          if (conversations.length) {
            conversations.forEach(conversation => this.__addConversationPage(conversation));
            if (this.__openConversationId) {
              const conversationsLayout = this.getChildControl("conversations-layout");
              const conversation = conversationsLayout.getSelectables().find(c => c.getConversationId() === this.__openConversationId);
              if (conversation) {
                conversationsLayout.setSelection([conversation]);
              }
              this.__openConversationId = null; // reset it so it does not open again
            }
          } else {
            this.__addTempConversationPage();
          }
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },

    __createConversationPage: function(conversationData) {
      const studyData = this.getStudyData();
      let conversationPage = null;
      if (conversationData) {
        const conversationId = conversationData["conversationId"];
        conversationPage = new osparc.conversation.Conversation(studyData, conversationId);
        conversationPage.setLabel(conversationData["name"]);
        osparc.store.Conversations.getInstance().addListener("conversationDeleted", e => {
          const data = e.getData();
          if (conversationId === data["conversationId"]) {
            this.__removeConversationPage(conversationId, true);
          }
        });
      } else {
        // create a temporary conversation
        conversationPage = new osparc.conversation.Conversation(studyData);
        conversationPage.setLabel(this.tr("new"));
      }
      return conversationPage;
    },

    __addTempConversationPage: function() {
      const temporaryConversationPage = this.__createConversationPage();
      this.__addToPages(temporaryConversationPage);
    },

    __addConversationPage: function(conversationData) {
      // ignore it if it was already there
      const conversationId = conversationData["conversationId"];
      const conversationPageFound = this.__getConversationPage(conversationId);
      if (conversationPageFound) {
        return null;
      }

      const conversationPage = this.__createConversationPage(conversationData);
      this.__addToPages(conversationPage);

      this.__conversationsPages.push(conversationPage);

      return conversationPage;
    },

    __addToPages: function(conversationPage) {
      const conversationsLayout = this.getChildControl("conversations-layout");
      if (conversationsLayout.getChildren().length === 1) {
        // remove the temporary conversation page
        if (conversationsLayout.getChildren()[0].getConversationId() === null) {
          conversationsLayout.remove(conversationsLayout.getChildren()[0]);
        }
      }
      conversationsLayout.add(conversationPage);

      if (this.__newConversationButton === null) {
          const studyData = this.getStudyData();
        // initialize the new button only once
        const newConversationButton = this.__newConversationButton = new qx.ui.form.Button().set({
          icon: "@FontAwesome5Solid/plus/12",
          toolTipText: this.tr("Add new conversation"),
          allowGrowX: false,
          backgroundColor: "transparent",
          enabled: osparc.data.model.Study.canIWrite(studyData["accessRights"]),
        });
        newConversationButton.addListener("execute", () => {
          osparc.store.Conversations.getInstance().addConversation(studyData["uuid"], "new " + (this.__conversationsPages.length + 1))
            .then(conversationDt => {
              this.__addConversationPage(conversationDt);
              const newConversationPage = this.__getConversationPage(conversationDt["conversationId"]);
              if (newConversationPage) {
                conversationsLayout.setSelection([newConversationPage]);
              }
            });
        });
        conversationsLayout.getChildControl("bar").add(newConversationButton);
      }
      // remove and add to move to last position
      const bar = conversationsLayout.getChildControl("bar");
      if (bar.indexOf(this.__newConversationButton) > -1) {
        bar.remove(this.__newConversationButton);
      }
      bar.add(this.__newConversationButton);
    },

    __removeConversationPage: function(conversationId, changeSelection = false) {
      const conversationPage = this.__getConversationPage(conversationId);
      if (conversationPage) {
        const conversationsLayout = this.getChildControl("conversations-layout");
        if (conversationsLayout.indexOf(conversationPage) > -1) {
          conversationsLayout.remove(conversationPage);
        }
        this.__conversationsPages = this.__conversationsPages.filter(c => c !== conversationPage);
        const conversationPages = conversationsLayout.getSelectables();
        if (conversationPages.length) {
          if (changeSelection) {
            // change selection to the first conversation
            conversationsLayout.setSelection([conversationPages[0]]);
          }
        } else {
          // no conversations left, add a temporary one
          this.__addTempConversationPage();
        }
      }
    },

    // it can only be renamed, not updated
    __updateConversationName: function(conversationData) {
      const conversationId = conversationData["conversationId"];
      const conversationPage = this.__getConversationPage(conversationId);
      if (conversationPage) {
        conversationPage.renameConversation(conversationData["name"]);
      }
    },

    // overridden
    destroy: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      if (this.__wsHandlers) {
        this.__wsHandlers.forEach(({ eventName }) => {
          socket.removeSlot(eventName);
        });
        this.__wsHandlers = null;
      }

      this.base(arguments);
    },
  },
});
