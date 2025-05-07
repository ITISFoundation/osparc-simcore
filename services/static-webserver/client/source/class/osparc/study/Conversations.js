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
    * @param studyData {String} Study Data
    */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.fetchConversations(studyData);
  },

  statics: {
    addConversation: function(studyId, name = "new 1") {
      const params = {
        url: {
          studyId,
        },
        data: {
          name,
          "type": "PROJECT_STATIC",
        }
      };
      return osparc.data.Resources.fetch("conversations", "addConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    deleteConversation: function(studyId, conversationId) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
      };
      return osparc.data.Resources.fetch("conversations", "deleteConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    renameConversation: function(studyId, conversationId, name) {
      const params = {
        url: {
          studyId,
          conversationId,
        },
        data: {
          name,
        }
      };
      return osparc.data.Resources.fetch("conversations", "renameConversation", params)
        .catch(err => osparc.FlashMessenger.logError(err));
    },
  },

  members: {
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

    fetchConversations: function(studyData) {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      const conversationsLayout = this.getChildControl("conversations-layout");
      const params = {
        url: {
          studyId: studyData["uuid"],
          offset: 0,
          limit: 42,
        }
      };
      osparc.data.Resources.fetch("conversations", "getConversationsPage", params)
        .then(conversations => {
          if (conversations.length === 0) {
            const noConversationTab = new osparc.info.Conversation(studyData);
            noConversationTab.setLabel(this.tr("new 1"));
            noConversationTab.addListener("conversationDeleted", () => {
              this._removeAll();
              this.fetchConversations(studyData);
            });
            conversationsLayout.add(noConversationTab);
          } else {
            conversations.forEach(conversation => {
              const conversationId = conversation["conversationId"];
              const conversationTab = new osparc.info.Conversation(studyData, conversationId);
              conversationTab.setLabel(conversation["name"]);
              conversationTab.addListener("conversationDeleted", () => {
                this._removeAll();
                this.fetchConversations(studyData);
              });
              conversationsLayout.add(conversationTab);
            });
          }
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },
  }
});
