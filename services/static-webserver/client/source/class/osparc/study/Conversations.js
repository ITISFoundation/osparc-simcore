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

      const params = {
        url: {
          studyId: studyData["uuid"],
          offset: 0,
          limit: 42,
        }
      };
      osparc.data.Resources.fetch("conversations", "getPage", params)
        .then(conversations => {
          const conversationsLayout = this.getChildControl("conversations-layout");
          console.log("Conversations fetched", conversations);
          if (conversations.length === 0) {
            const noConversationTab = new osparc.info.Conversation(studyData);
            noConversationTab.setLabel(this.tr("new 1"));
            conversationsLayout.add(noConversationTab);
          } else {
            conversations.forEach(conversation => {
              const conversationId = conversation["id"];
              const conversationTab = new osparc.info.Conversation(studyData, conversationId);
              conversationTab.setLabel(conversation["name"]);
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
