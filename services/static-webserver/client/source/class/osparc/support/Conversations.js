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


qx.Class.define("osparc.support.Conversations", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__noConversationsLabel = new qx.ui.basic.Label("No conversations yet — your messages will appear here.").set({
      padding: 5,
    });
    this.__conversationListItems = [];

    this.__fetchConversations();

    this.__listenToNewConversations();
  },

  events: {
    "openConversation": "qx.event.type.Data",
  },

  members: {
    __noConversationsLabel: null,
    __conversationListItems: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __getConversationItem: function(conversationId) {
      return this.__conversationListItems.find(conversation => conversation.getConversation().getConversationId() === conversationId);
    },

    __fetchConversations: function() {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      osparc.store.ConversationsSupport.getInstance().getConversations()
        .then(conversations => {
          if (conversations.length) {
            conversations.forEach(conversation => this.__addConversation(conversation));
          } else {
            // No conversations found
            this.getChildControl("conversations-layout").add(this.__noConversationsLabel);
          }
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },

    __listenToNewConversations: function() {
      osparc.store.ConversationsSupport.getInstance().addListener("conversationCreated", e => {
        const conversation = e.getData();
        this.__addConversation(conversation);
      });
    },

    __addConversation: function(conversation) {
      const conversationsLayout = this.getChildControl("conversations-layout");
      // remove the noConversationsLabel
      if (conversationsLayout && conversationsLayout.getChildren().indexOf(this.__noConversationsLabel) > -1) {
        conversationsLayout.remove(this.__noConversationsLabel);
      }

      // ignore it if it was already there
      const conversationId = conversation.getConversationId();
      const conversationItemFound = this.__getConversationItem(conversationId);
      if (conversationItemFound) {
        return null;
      }

      const conversationListItem = new osparc.support.ConversationListItem();
      conversationListItem.setConversation(conversation);
      conversationListItem.addListener("tap", () => this.fireDataEvent("openConversation", conversationId, this));
      conversationsLayout.add(conversationListItem);
      this.__conversationListItems.push(conversationListItem);

      return conversationListItem;
    },
  },
});
